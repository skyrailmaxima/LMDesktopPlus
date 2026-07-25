"""Audio volume/mute adapter — wpctl preferred, pactl fallback.

@use levels: snapshot/set_volume/toggle_mute are high use (desktop chrome).
Preoptimized: parsers/probes return Outcome; host calls use try_run (no raises).
Branch style: ternary + one loop per subfunction (first_ok_scan).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import Outcome, clamp_int, first_ok_scan, map_get, parse_float, parse_int, try_run
from ..util import executable
from .base import command_error, dispatch_command

_WPCTL_VOLUME = re.compile(r"\bVolume:\s*([0-9]+(?:\.[0-9]+)?)")
_PACTL_VOLUME = re.compile(r"/\s*([0-9]+)%")
_PACTL_MUTE = re.compile(r"\bMute:\s*(yes|no)\b", re.IGNORECASE)

# Preferred probe/control order — first success wins (priority table).
_BACKEND_ORDER = ("wpctl", "pactl")

# Preoptimized argv templates: (argv format slots). {binary} / {volume} filled later.
_SET_VOLUME_TMPL: dict[str, tuple[str, ...]] = {
    "wpctl": ("{binary}", "set-volume", "@DEFAULT_AUDIO_SINK@", "{volume}%"),
    "pactl": ("{binary}", "set-sink-volume", "@DEFAULT_SINK@", "{volume}%"),
}
_TOGGLE_MUTE_TMPL: dict[str, tuple[str, ...]] = {
    "wpctl": ("{binary}", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"),
    "pactl": ("{binary}", "set-sink-mute", "@DEFAULT_SINK@", "toggle"),
}


@register_fn(
    "audio.parse_wpctl_volume",
    UseLevel.HIGH,
    "Parse wpctl get-volume into percent + muted (None on miss)",
)
def parse_wpctl_volume(output: str) -> tuple[int, bool] | None:
    # @use: high use — purpose: desktop volume bar from wpctl stdout
    match = _WPCTL_VOLUME.search(output)
    if match is None:
        return None
    ratio = parse_float(match.group(1))
    return None if ratio is None else (
        clamp_int(round(ratio * 100), 0, 100),
        "[MUTED]" in output.upper(),
    )


@register_fn(
    "audio.parse_pactl_volume",
    UseLevel.HIGH,
    "Parse pactl get-sink-volume into percent (None on miss)",
)
def parse_pactl_volume(output: str) -> int | None:
    # @use: high use — purpose: desktop volume bar from pactl stdout
    match = _PACTL_VOLUME.search(output)
    if match is None:
        return None
    value = parse_int(match.group(1))
    return None if value is None else clamp_int(value, 0, 100)


@register_fn(
    "audio.parse_pactl_mute",
    UseLevel.HIGH,
    "Parse pactl get-sink-mute into boolean (None on miss)",
)
def parse_pactl_mute(output: str) -> bool | None:
    # @use: high use — purpose: mute chip from pactl stdout
    match = _PACTL_MUTE.search(output)
    return None if match is None else (match.group(1).lower() == "yes")


def probe_wpctl(binary: str) -> Outcome:
    # @use: high use — purpose: one-shot wpctl volume+mute probe (no raises)
    run = try_run([binary, "get-volume", "@DEFAULT_AUDIO_SINK@"], timeout=3)
    if not run.ok:
        return Outcome.fail(run.error or run.stderr.strip() or "wpctl get-volume failed")
    parsed = parse_wpctl_volume(run.stdout)
    return (
        Outcome.success(parsed)
        if parsed is not None
        else Outcome.fail("wpctl output did not contain a volume")
    )


def probe_pactl(binary: str) -> Outcome:
    # @use: high use — purpose: one-shot pactl volume+mute probe (no raises)
    volume_run = try_run([binary, "get-sink-volume", "@DEFAULT_SINK@"], timeout=3)
    mute_run = try_run([binary, "get-sink-mute", "@DEFAULT_SINK@"], timeout=3)
    if not volume_run.ok or not mute_run.ok:
        detail = (
            volume_run.error
            or volume_run.stderr.strip()
            or mute_run.error
            or mute_run.stderr.strip()
            or "pactl sink query failed"
        )
        return Outcome.fail(detail)
    volume = parse_pactl_volume(volume_run.stdout)
    muted = parse_pactl_mute(mute_run.stdout)
    return (
        Outcome.success((volume, muted))
        if volume is not None and muted is not None
        else Outcome.fail("pactl output did not contain volume/mute")
    )


# Backend id → exception-free probe (Outcome carries value or error).
_PROBE: dict[str, Callable[[str], Outcome]] = {
    "wpctl": probe_wpctl,
    "pactl": probe_pactl,
}


def etch_set_volume_argv(backend: str, binary: str, volume: int) -> list[str] | None:
    # @use: high use — purpose: template fill from preoptimized argv table
    tmpl = map_get(_SET_VOLUME_TMPL, backend)
    return None if tmpl is None else [
        part.format(binary=binary, volume=volume) for part in tmpl
    ]


def etch_toggle_mute_argv(backend: str, binary: str) -> list[str] | None:
    # @use: high use — purpose: mute-toggle argv from preoptimized table
    tmpl = map_get(_TOGGLE_MUTE_TMPL, backend)
    return None if tmpl is None else [part.format(binary=binary) for part in tmpl]


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
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        snapshot = self._probe_first_backend()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_first_backend(self) -> dict[str, Any]:
        # @use: high use — purpose: one-loop wpctl→pactl priority probe
        result = first_ok_scan(
            _BACKEND_ORDER,
            self._probe_named_backend,
            empty_error="no audio backend succeeded",
        )
        if not result.ok:
            return {
                "available": False,
                "backend": self.backend,
                "last_error": result.error,
            }
        backend, volume, muted = result.value
        self.backend = backend
        return {
            "available": True,
            "backend": backend,
            "volume": volume,
            "muted": muted,
        }

    def _probe_named_backend(self, backend: str) -> Outcome:
        # @use: high use — purpose: single-backend probe step for first_ok_scan
        binary = self.binaries.get(backend)
        probe = map_get(_PROBE, backend)
        if not binary or probe is None:
            return Outcome.fail(f"{backend}: missing")
        probed = probe(binary)
        if not probed.ok:
            return Outcome.fail(f"{backend}: {probed.error}")
        volume, muted = probed.value
        return Outcome.success((backend, volume, muted))

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
        # Payload volume must be a real int (JSON bool is rejected).
        volume = None if isinstance(value, bool) or not isinstance(value, int) else value
        return (
            command_error("invalid_argument", "volume must be an integer")
            if volume is None
            else self._run_first_backend(
                lambda backend, binary: etch_set_volume_argv(
                    backend, binary, clamp_int(volume, 0, 100)
                ),
                ok_extra={"volume": clamp_int(volume, 0, 100)},
            )
        )

    def _toggle_mute(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: mute toggle across backends
        return (
            command_error("unavailable", "no supported audio control tool found")
            if not self.available()
            else self._run_first_backend(etch_toggle_mute_argv)
        )

    def _run_first_backend(
        self,
        argv_for: Callable[[str, str], list[str] | None],
        *,
        ok_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # @use: high use — purpose: one-loop command fallback wpctl→pactl
        result = first_ok_scan(
            _BACKEND_ORDER,
            lambda backend: self._run_named_backend(backend, argv_for),
            empty_error="no audio backend succeeded",
        )
        if not result.ok:
            return command_error("unavailable", result.error)
        self.backend = result.value
        self._cached_snapshot = None
        response: dict[str, Any] = {"ok": True}
        return response if ok_extra is None else {**response, **ok_extra}

    def _run_named_backend(
        self,
        backend: str,
        argv_for: Callable[[str, str], list[str] | None],
    ) -> Outcome:
        # @use: high use — purpose: single-backend command step for first_ok_scan
        binary = self.binaries.get(backend)
        if not binary:
            return Outcome.fail(f"{backend}: missing")
        argv = argv_for(backend, binary)
        if argv is None:
            return Outcome.fail(f"{backend}: unknown backend")
        run = try_run(argv, timeout=3)
        return (
            Outcome.success(backend)
            if run.ok
            else Outcome.fail(f"{backend}: {run.error or run.stderr.strip() or 'audio command failed'}")
        )
