"""Display brightness adapter — brightnessctl preferred, sysfs read-only fallback.

@use levels: snapshot/set_brightness are high use (desktop chrome).
Writes only go through brightnessctl; sysfs never receives writes.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
from ..util import executable, run_capture
from .base import command_error, dispatch_command

_AUTO = object()


@register_fn(
    "display.brightness_percentage",
    UseLevel.HIGH,
    "Convert current/max brightness integers into 0–100 percent",
)
def brightness_percentage(current: int, maximum: int) -> int:
    # @use: high use — purpose: normalize brightnessctl/sysfs readings for UI
    if maximum <= 0:
        raise ValueError("maximum brightness must be positive")
    return max(0, min(100, round(current * 100 / maximum)))


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
        # @use: medium use — purpose: locate first readable backlight device
        try:
            devices = sorted(path for path in self.sysfs_root.iterdir() if path.is_dir())
        except OSError:
            return None
        for device in devices:
            if (device / "brightness").is_file() and (device / "max_brightness").is_file():
                return device
        return None

    def available(self) -> bool:
        return isinstance(self.brightnessctl, str) or self._sysfs_device() is not None

    @staticmethod
    def _percentage(current: int, maximum: int) -> int:
        return brightness_percentage(current, maximum)

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: desktop brightness poll with short TTL
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        snapshot = self._probe_brightness()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_brightness(self) -> dict[str, Any]:
        # @use: high use — purpose: brightnessctl then sysfs fail-soft probe
        errors: list[str] = []
        ctl = self._probe_brightnessctl(errors)
        if ctl is not None:
            return ctl
        sysfs = self._probe_sysfs(errors)
        if sysfs is not None:
            return sysfs
        return {
            "available": False,
            "last_error": "; ".join(errors) or "no display brightness control found",
        }

    def _probe_brightnessctl(self, errors: list[str]) -> dict[str, Any] | None:
        # @use: high use — purpose: writable brightnessctl read path
        if not isinstance(self.brightnessctl, str):
            return None
        try:
            current = run_capture([self.brightnessctl, "g"], timeout=3)
            maximum = run_capture([self.brightnessctl, "m"], timeout=3)
            if current.returncode != 0 or maximum.returncode != 0:
                detail = current.stderr.strip() or maximum.stderr.strip()
                raise RuntimeError(detail or "brightnessctl query failed")
            brightness = self._percentage(
                int(current.stdout.strip()),
                int(maximum.stdout.strip()),
            )
            return {
                "available": True,
                "backend": "brightnessctl",
                "brightness": brightness,
                "writable": True,
            }
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(f"brightnessctl: {exc}")
            return None

    def _probe_sysfs(self, errors: list[str]) -> dict[str, Any] | None:
        # @use: medium use — purpose: read-only sysfs brightness fallback
        device = self._sysfs_device()
        if device is None:
            return None
        try:
            brightness = self._percentage(
                int((device / "brightness").read_text(encoding="utf-8").strip()),
                int((device / "max_brightness").read_text(encoding="utf-8").strip()),
            )
            return {
                "available": True,
                "backend": "sysfs",
                "brightness": brightness,
                "writable": False,
            }
        except (OSError, ValueError) as exc:
            errors.append(f"sysfs: {exc}")
            return None

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
        if isinstance(value, bool) or not isinstance(value, int):
            return command_error("invalid_argument", "brightness must be an integer")
        brightness = max(1, min(100, value))
        # Refuse writes when the last probe (or live probe) is read-only sysfs.
        refuse = self._refuse_write_reason()
        if refuse is not None:
            return command_error("unavailable", refuse)
        assert isinstance(self.brightnessctl, str)
        try:
            result = run_capture(
                [self.brightnessctl, "s", f"{brightness}%"],
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return command_error("internal_error", f"brightnessctl: {exc}")
        if result.returncode != 0:
            return command_error(
                "internal_error",
                result.stderr.strip() or "brightnessctl command failed",
            )
        self._cached_snapshot = None
        return {"ok": True, "brightness": brightness}

    def _refuse_write_reason(self) -> str | None:
        # @use: medium use — purpose: guard sysfs/unavailable write attempts
        if self._cached_snapshot is not None and not self._cached_snapshot.get(
            "writable", False
        ):
            if self._cached_snapshot.get("backend") == "sysfs":
                return "sysfs brightness fallback is read-only"
            return "display brightness control is unavailable"
        if not isinstance(self.brightnessctl, str):
            if self._sysfs_device() is not None:
                return "sysfs brightness fallback is read-only"
            return "no supported brightness control tool found"
        return None
