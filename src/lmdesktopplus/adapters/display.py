"""Display brightness adapter — brightnessctl preferred, sysfs read-only fallback.

@use levels: snapshot/set_brightness are high use (desktop chrome).
Preoptimized: try_run + Outcome probes; one loop max via first_ok_scan.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import Outcome, clamp_int, first_ok_scan, parse_int, try_run
from ..util import executable
from .base import command_error, dispatch_command

_AUTO = object()


@register_fn(
    "display.brightness_percentage",
    UseLevel.HIGH,
    "Convert current/max brightness integers into 0–100 percent",
)
def brightness_percentage(current: int, maximum: int) -> int | None:
    # @use: high use — purpose: normalize brightnessctl/sysfs readings for UI
    return None if maximum <= 0 else clamp_int(round(current * 100 / maximum), 0, 100)


class DisplayAdapter:
    """Desktop brightness chrome with fail-soft read-only sysfs fallback."""

    id = "display"

    def __init__(
        self,
        cache_ttl: float = 0.75,
        brightnessctl: str | None | object = _AUTO,
        sysfs_root: Path = Path("/sys/class/backlight"),
    ) -> None:
        self.brightnessctl = (
            executable("brightnessctl") if brightnessctl is _AUTO else brightnessctl
        )
        self.sysfs_root = sysfs_root
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def _sysfs_device(self) -> Path | None:
        # @use: medium use — purpose: first readable backlight device (one loop)
        try:
            devices = sorted(path for path in self.sysfs_root.iterdir() if path.is_dir())
        except OSError:
            return None
        for device in devices:
            ready = (device / "brightness").is_file() and (device / "max_brightness").is_file()
            if ready:
                return device
        return None

    def available(self) -> bool:
        return isinstance(self.brightnessctl, str) or self._sysfs_device() is not None

    @staticmethod
    def _percentage(current: int, maximum: int) -> int:
        percent = brightness_percentage(current, maximum)
        if percent is None:
            raise ValueError("maximum brightness must be positive")
        return percent

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: desktop brightness poll with short TTL
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        snapshot = self._probe_brightness()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_brightness(self) -> dict[str, Any]:
        # @use: high use — purpose: one-loop priority probe brightnessctl→sysfs
        result = first_ok_scan(
            ("brightnessctl", "sysfs"),
            self._probe_named_backend,
            empty_error="no display brightness control found",
        )
        return (
            result.value
            if result.ok
            else {"available": False, "last_error": result.error}
        )

    def _probe_named_backend(self, backend: str) -> Outcome:
        # @use: high use — purpose: single brightness backend step
        probes = {
            "brightnessctl": self._probe_brightnessctl,
            "sysfs": self._probe_sysfs,
        }
        probe = probes.get(backend)
        return Outcome.fail(f"{backend}: unknown") if probe is None else probe()

    def _probe_brightnessctl(self) -> Outcome:
        # @use: high use — purpose: writable brightnessctl read path (no raises)
        if not isinstance(self.brightnessctl, str):
            return Outcome.fail("brightnessctl: missing")
        current = try_run([self.brightnessctl, "g"], timeout=3)
        maximum = try_run([self.brightnessctl, "m"], timeout=3)
        if not current.ok or not maximum.ok:
            detail = (
                current.error
                or current.stderr.strip()
                or maximum.error
                or maximum.stderr.strip()
                or "brightnessctl query failed"
            )
            return Outcome.fail(f"brightnessctl: {detail}")
        cur_i = parse_int(current.stdout.strip())
        max_i = parse_int(maximum.stdout.strip())
        percent = (
            None
            if cur_i is None or max_i is None
            else brightness_percentage(cur_i, max_i)
        )
        return (
            Outcome.fail("brightnessctl: invalid brightness integers")
            if percent is None
            else Outcome.success(
                {
                    "available": True,
                    "backend": "brightnessctl",
                    "brightness": percent,
                    "writable": True,
                }
            )
        )

    def _probe_sysfs(self) -> Outcome:
        # @use: medium use — purpose: read-only sysfs brightness fallback
        device = self._sysfs_device()
        if device is None:
            return Outcome.fail("sysfs: no device")
        cur_i = self._read_sysfs_int(device / "brightness")
        max_i = self._read_sysfs_int(device / "max_brightness")
        percent = (
            None
            if cur_i is None or max_i is None
            else brightness_percentage(cur_i, max_i)
        )
        return (
            Outcome.fail("sysfs: unreadable brightness")
            if percent is None
            else Outcome.success(
                {
                    "available": True,
                    "backend": "sysfs",
                    "brightness": percent,
                    "writable": False,
                }
            )
        )

    @staticmethod
    def _read_sysfs_int(path: Path) -> int | None:
        # @use: medium use — purpose: sysfs int read without bubbling OSError
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return parse_int(text)

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: brightness slider via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "set_brightness": self._set_brightness,
        }

    def _set_brightness(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: clamp + write brightness through brightnessctl only
        value = payload.get("brightness")
        brightness = None if isinstance(value, bool) or not isinstance(value, int) else value
        if brightness is None:
            return command_error("invalid_argument", "brightness must be an integer")
        brightness = clamp_int(brightness, 1, 100)
        refuse = self._refuse_write_reason()
        return (
            command_error("unavailable", refuse)
            if refuse is not None
            else self._write_brightnessctl(brightness)
        )

    def _write_brightnessctl(self, brightness: int) -> dict[str, Any]:
        # @use: high use — purpose: brightnessctl s N% via try_run
        assert isinstance(self.brightnessctl, str)
        run = try_run([self.brightnessctl, "s", f"{brightness}%"], timeout=3)
        if not run.launched:
            return command_error("internal_error", f"brightnessctl: {run.error}")
        if not run.ok:
            return command_error(
                "internal_error",
                run.stderr.strip() or "brightnessctl command failed",
            )
        self._cached_snapshot = None
        return {"ok": True, "brightness": brightness}

    def _refuse_write_reason(self) -> str | None:
        # @use: medium use — purpose: guard sysfs/unavailable write attempts
        cached = self._cached_snapshot
        if cached is not None and not cached.get("writable", False):
            return (
                "sysfs brightness fallback is read-only"
                if cached.get("backend") == "sysfs"
                else "display brightness control is unavailable"
            )
        if isinstance(self.brightnessctl, str):
            return None
        return (
            "sysfs brightness fallback is read-only"
            if self._sysfs_device() is not None
            else "no supported brightness control tool found"
        )
