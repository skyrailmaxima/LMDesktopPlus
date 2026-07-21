from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from ..util import first_executable, run_capture

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

    def __init__(self, cache_ttl: float = 0.75) -> None:
        self.binary = first_executable(["wpctl", "pactl"])
        self.backend = Path(self.binary).name if self.binary else None
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return self.binary is not None

    def snapshot(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            if self.backend == "wpctl":
                result = run_capture(
                    [self.binary, "get-volume", "@DEFAULT_AUDIO_SINK@"],
                    timeout=3,
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip() or "wpctl get-volume failed")
                volume, muted = parse_wpctl_volume(result.stdout)
            else:
                volume_result = run_capture(
                    [self.binary, "get-sink-volume", "@DEFAULT_SINK@"],
                    timeout=3,
                )
                mute_result = run_capture(
                    [self.binary, "get-sink-mute", "@DEFAULT_SINK@"],
                    timeout=3,
                )
                if volume_result.returncode != 0 or mute_result.returncode != 0:
                    error = volume_result.stderr.strip() or mute_result.stderr.strip()
                    raise RuntimeError(error or "pactl sink query failed")
                volume = parse_pactl_volume(volume_result.stdout)
                muted = parse_pactl_mute(mute_result.stdout)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            snapshot = {
                "available": False,
                "backend": self.backend,
                "last_error": str(exc),
            }
        else:
            snapshot = {
                "available": True,
                "backend": self.backend,
                "volume": volume,
                "muted": muted,
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
            if self.backend == "wpctl":
                argv = [self.binary, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%"]
            else:
                argv = [self.binary, "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"]
        elif self.backend == "wpctl":
            argv = [self.binary, "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
        else:
            argv = [self.binary, "set-sink-mute", "@DEFAULT_SINK@", "toggle"]

        try:
            result = run_capture(argv, timeout=3)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "audio command failed"}
        self._cached_snapshot = None
        response: dict[str, Any] = {"ok": True}
        if name == "set_volume":
            response["volume"] = volume
        return response
