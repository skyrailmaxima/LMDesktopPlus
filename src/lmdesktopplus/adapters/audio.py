"""Audio volume/mute adapter — wpctl preferred, pactl fallback.

@use levels: snapshot/set_volume/toggle_mute are high use (desktop chrome).
Command resolution uses dispatch_command; backend argv comes from hash maps.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from typing import Any

from ..fncache import UseLevel, register_fn
from ..util import executable, run_capture
from .base import command_error, dispatch_command

_WPCTL_VOLUME = re.compile(r"\bVolume:\s*([0-9]+(?:\.[0-9]+)?)")
_PACTL_VOLUME = re.compile(r"/\s*([0-9]+)%")
_PACTL_MUTE = re.compile(r"\bMute:\s*(yes|no)\b", re.IGNORECASE)

# Preferred probe/control order — first success wins.
_BACKEND_ORDER = ("wpctl", "pactl")


@register_fn(
    "audio.parse_wpctl_volume",
    UseLevel.HIGH,
    "Parse wpctl get-volume into percent + muted",
)
def parse_wpctl_volume(output: str) -> tuple[int, bool]:
    # @use: high use — purpose: desktop volume bar from wpctl stdout
    match = _WPCTL_VOLUME.search(output)
    if not match:
        raise ValueError("wpctl output did not contain a volume")
    volume = round(float(match.group(1)) * 100)
    return max(0, min(100, volume)), "[MUTED]" in output.upper()


@register_fn(
    "audio.parse_pactl_volume",
    UseLevel.HIGH,
    "Parse pactl get-sink-volume into percent",
)
def parse_pactl_volume(output: str) -> int:
    # @use: high use — purpose: desktop volume bar from pactl stdout
    match = _PACTL_VOLUME.search(output)
    if not match:
        raise ValueError("pactl output did not contain a volume")
    return max(0, min(100, int(match.group(1))))


@register_fn(
    "audio.parse_pactl_mute",
    UseLevel.HIGH,
    "Parse pactl get-sink-mute into boolean",
)
def parse_pactl_mute(output: str) -> bool:
    # @use: high use — purpose: mute chip from pactl stdout
    match = _PACTL_MUTE.search(output)
    if not match:
        raise ValueError("pactl output did not contain mute state")
    return match.group(1).lower() == "yes"


def probe_wpctl(binary: str) -> tuple[int, bool]:
    # @use: high use — purpose: one-shot wpctl volume+mute probe
    result = run_capture([binary, "get-volume", "@DEFAULT_AUDIO_SINK@"], timeout=3)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "wpctl get-volume failed")
    return parse_wpctl_volume(result.stdout)


def probe_pactl(binary: str) -> tuple[int, bool]:
    # @use: high use — purpose: one-shot pactl volume+mute probe
    volume_result = run_capture([binary, "get-sink-volume", "@DEFAULT_SINK@"], timeout=3)
    mute_result = run_capture([binary, "get-sink-mute", "@DEFAULT_SINK@"], timeout=3)
    if volume_result.returncode != 0 or mute_result.returncode != 0:
        error = volume_result.stderr.strip() or mute_result.stderr.strip()
        raise RuntimeError(error or "pactl sink query failed")
    return parse_pactl_volume(volume_result.stdout), parse_pactl_mute(mute_result.stdout)


# Backend id → probe callable (volume percent, muted).
_PROBE: dict[str, Callable[[str], tuple[int, bool]]] = {
    "wpctl": probe_wpctl,
    "pactl": probe_pactl,
}


def etch_set_volume_argv(backend: str, binary: str, volume: int) -> list[str]:
    # @use: high use — purpose: (backend, volume) → host argv without if/elif trees
    builders = {
        "wpctl": lambda: [binary, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%"],
        "pactl": lambda: [binary, "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
    }
    builder = builders.get(backend)
    if builder is None:
        raise KeyError(backend)
    return builder()


def etch_toggle_mute_argv(backend: str, binary: str) -> list[str]:
    # @use: high use — purpose: backend → mute-toggle argv
    builders = {
        "wpctl": lambda: [binary, "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"],
        "pactl": lambda: [binary, "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
    }
    builder = builders.get(backend)
    if builder is None:
        raise KeyError(backend)
    return builder()


class AudioAdapter:
    """Desktop audio chrome — PipeWire/WirePlumber via wpctl, Pulse via pactl."""

    id = "audio"

    def __init__(
        self,
        cache_ttl: float = 0.75,
        binaries: dict[str, str] | None = None,
    ) -> None:
        self.binaries = binaries if binaries is not None else {
            name: path
            for name in _BACKEND_ORDER
            if (path := executable(name)) is not None
        }
        self.backend = next(iter(self.binaries), None)
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.binaries)

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: desktop volume/mute poll with short TTL
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        # Walk preferred backends; first successful probe wins.
        snapshot = self._probe_first_backend()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_first_backend(self) -> dict[str, Any]:
        # @use: high use — purpose: fail-soft dual-backend volume probe
        errors: list[str] = []
        for backend in _BACKEND_ORDER:
            binary = self.binaries.get(backend)
            probe = _PROBE.get(backend)
            if not binary or probe is None:
                continue
            try:
                volume, muted = probe(binary)
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{backend}: {exc}")
                continue
            self.backend = backend
            return {
                "available": True,
                "backend": backend,
                "volume": volume,
                "muted": muted,
            }
        return {
            "available": False,
            "backend": self.backend,
            "last_error": "; ".join(errors) or "no audio backend succeeded",
        }

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: volume/mute clicks via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "set_volume": self._set_volume,
            "toggle_mute": self._toggle_mute,
        }

    def _set_volume(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: clamp + apply volume across backends
        if not self.available():
            return command_error("unavailable", "no supported audio control tool found")
        value = payload.get("volume")
        if isinstance(value, bool) or not isinstance(value, int):
            return command_error("invalid_argument", "volume must be an integer")
        volume = max(0, min(100, value))
        return self._run_first_backend(
            lambda backend, binary: etch_set_volume_argv(backend, binary, volume),
            ok_extra={"volume": volume},
        )

    def _toggle_mute(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: mute toggle across backends
        if not self.available():
            return command_error("unavailable", "no supported audio control tool found")
        return self._run_first_backend(etch_toggle_mute_argv)

    def _run_first_backend(
        self,
        argv_for: Callable[[str, str], list[str]],
        *,
        ok_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # @use: high use — purpose: try wpctl then pactl until one command succeeds
        errors: list[str] = []
        for backend in _BACKEND_ORDER:
            binary = self.binaries.get(backend)
            if not binary:
                continue
            try:
                argv = argv_for(backend, binary)
                result = run_capture(argv, timeout=3)
            except (OSError, subprocess.TimeoutExpired, KeyError) as exc:
                errors.append(f"{backend}: {exc}")
                continue
            if result.returncode != 0:
                errors.append(f"{backend}: {result.stderr.strip() or 'audio command failed'}")
                continue
            self.backend = backend
            self._cached_snapshot = None
            response: dict[str, Any] = {"ok": True}
            if ok_extra:
                response.update(ok_extra)
            return response
        return command_error(
            "unavailable",
            "; ".join(errors) or "no audio backend succeeded",
        )
