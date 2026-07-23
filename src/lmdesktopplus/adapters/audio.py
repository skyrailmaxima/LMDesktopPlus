from __future__ import annotations

import re
import subprocess
import time
from typing import Any

from ..util import executable, run_capture

_WPCTL_VOLUME = re.compile(r"\bVolume:\s*([0-9]+(?:\.[0-9]+)?)")
_PACTL_VOLUME = re.compile(r"/\s*([0-9]+)%")
_PACTL_MUTE = re.compile(r"\bMute:\s*(yes|no)\b", re.IGNORECASE)


def parse_wpctl_volume(output: str) -> tuple[int, bool]:
    match = _WPCTL_VOLUME.search(output)
    if not match:
        raise ValueError("wpctl output did not contain a volume")
    volume = round(float(match.group(1)) * 100)
    return max(0, min(100, volume)), "[MUTED]" in output.upper()


def parse_pactl_volume(output: str) -> int:
    match = _PACTL_VOLUME.search(output)
    if not match:
        raise ValueError("pactl output did not contain a volume")
    return max(0, min(100, int(match.group(1))))


def parse_pactl_mute(output: str) -> bool:
    match = _PACTL_MUTE.search(output)
    if not match:
        raise ValueError("pactl output did not contain mute state")
    return match.group(1).lower() == "yes"


class AudioAdapter:
    id = "audio"

    def __init__(
        self,
        cache_ttl: float = 0.75,
        binaries: dict[str, str] | None = None,
    ) -> None:
        self.binaries = binaries if binaries is not None else {
            name: path
            for name in ("wpctl", "pactl")
            if (path := executable(name)) is not None
        }
        self.backend = next(iter(self.binaries), None)
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.binaries)

    def snapshot(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        errors: list[str] = []
        for backend in ("wpctl", "pactl"):
            binary = self.binaries.get(backend)
            if not binary:
                continue
            try:
                if backend == "wpctl":
                    result = run_capture(
                        [binary, "get-volume", "@DEFAULT_AUDIO_SINK@"],
                        timeout=3,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or "wpctl get-volume failed")
                    volume, muted = parse_wpctl_volume(result.stdout)
                else:
                    volume_result = run_capture(
                        [binary, "get-sink-volume", "@DEFAULT_SINK@"],
                        timeout=3,
                    )
                    mute_result = run_capture(
                        [binary, "get-sink-mute", "@DEFAULT_SINK@"],
                        timeout=3,
                    )
                    if volume_result.returncode != 0 or mute_result.returncode != 0:
                        error = volume_result.stderr.strip() or mute_result.stderr.strip()
                        raise RuntimeError(error or "pactl sink query failed")
                    volume = parse_pactl_volume(volume_result.stdout)
                    muted = parse_pactl_mute(mute_result.stdout)
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{backend}: {exc}")
                continue
            self.backend = backend
            snapshot = {
                "available": True,
                "backend": backend,
                "volume": volume,
                "muted": muted,
            }
            break
        else:
            snapshot = {
                "available": False,
                "backend": self.backend,
                "last_error": "; ".join(errors) or "no audio backend succeeded",
            }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in {"set_volume", "toggle_mute"}:
            return {"ok": False, "error": f"unknown audio command: {name}"}
        if not self.available():
            return {"ok": False, "error": "no supported audio control tool found"}

        if name == "set_volume":
            value = payload.get("volume")
            if isinstance(value, bool) or not isinstance(value, int):
                return {"ok": False, "error": "volume must be an integer"}
            volume = max(0, min(100, value))
        errors: list[str] = []
        for backend in ("wpctl", "pactl"):
            binary = self.binaries.get(backend)
            if not binary:
                continue
            if name == "set_volume":
                argv = (
                    [binary, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%"]
                    if backend == "wpctl"
                    else [binary, "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"]
                )
            elif backend == "wpctl":
                argv = [binary, "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
            else:
                argv = [binary, "set-sink-mute", "@DEFAULT_SINK@", "toggle"]
            try:
                result = run_capture(argv, timeout=3)
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{backend}: {exc}")
                continue
            if result.returncode != 0:
                errors.append(f"{backend}: {result.stderr.strip() or 'audio command failed'}")
                continue
            self.backend = backend
            self._cached_snapshot = None
            response: dict[str, Any] = {"ok": True}
            if name == "set_volume":
                response["volume"] = volume
            return response
        return {"ok": False, "error": "; ".join(errors) or "no audio backend succeeded"}
