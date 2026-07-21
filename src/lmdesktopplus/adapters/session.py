from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..util import app_data_dir


class SessionAdapter:
    id = "session"

    @staticmethod
    def _flag_path() -> Path:
        return app_data_dir() / "start-hyprland-once"

    def available(self) -> bool:
        return True

    def snapshot(self) -> dict[str, Any]:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        desktop_names = {name.strip().lower() for name in desktop.split(":") if name.strip()}
        return {
            "available": True,
            "hyprland_active": bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
            or "hyprland" in desktop_names,
            "cinnamon_active": any("cinnamon" in name for name in desktop_names),
            "armed": self._flag_path().is_file(),
            "desktop": desktop,
            "tty_hint": "Ctrl+Alt+F3",
        }

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name == "status":
            return {"ok": True, **self.snapshot()}
        if name != "arm_hyprland":
            return {"ok": False, "error": f"unknown session command: {name}"}

        flag = self._flag_path()
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch(exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": f"could not arm Hyprland one-shot: {exc}"}
        return {
            "ok": True,
            "armed": True,
            "flag": str(flag),
            "instructions": "Press Ctrl+Alt+F3, then log in.",
        }
