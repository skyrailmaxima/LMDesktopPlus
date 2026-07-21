from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from ..util import executable, run_capture


_AUTO = object()


class DisplayAdapter:
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
        if maximum <= 0:
            raise ValueError("maximum brightness must be positive")
        return max(0, min(100, round(current * 100 / maximum)))

    def snapshot(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()

        errors: list[str] = []
        snapshot: dict[str, Any] | None = None
        if isinstance(self.brightnessctl, str):
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
                snapshot = {
                    "available": True,
                    "backend": "brightnessctl",
                    "brightness": brightness,
                    "writable": True,
                }
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(f"brightnessctl: {exc}")

        if snapshot is None:
            device = self._sysfs_device()
            if device is not None:
                try:
                    brightness = self._percentage(
                        int((device / "brightness").read_text(encoding="utf-8").strip()),
                        int((device / "max_brightness").read_text(encoding="utf-8").strip()),
                    )
                    snapshot = {
                        "available": True,
                        "backend": "sysfs",
                        "brightness": brightness,
                        "writable": False,
                    }
                except (OSError, ValueError) as exc:
                    errors.append(f"sysfs: {exc}")

        if snapshot is None:
            snapshot = {
                "available": False,
                "last_error": "; ".join(errors) or "no display brightness control found",
            }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name != "set_brightness":
            return {"ok": False, "error": f"unknown display command: {name}"}
        value = payload.get("brightness")
        if isinstance(value, bool) or not isinstance(value, int):
            return {"ok": False, "error": "brightness must be an integer"}
        brightness = max(1, min(100, value))
        if not isinstance(self.brightnessctl, str):
            if self._sysfs_device() is not None:
                return {"ok": False, "error": "sysfs brightness fallback is read-only"}
            return {"ok": False, "error": "no supported brightness control tool found"}
        try:
            result = run_capture(
                [self.brightnessctl, "s", f"{brightness}%"],
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": f"brightnessctl: {exc}"}
        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or "brightnessctl command failed",
            }
        self._cached_snapshot = None
        return {"ok": True, "brightness": brightness}
