from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import command_error, envelope
from ..util import app_data_dir, executable


class SessionAdapter:
    id = "session"

    @staticmethod
    def _flag_path() -> Path:
        return app_data_dir() / "start-hyprland-once"

    def available(self) -> bool:
        return True

    def _lifecycle_status(self, snap: dict[str, Any]) -> str:
        if snap["hyprland_active"]:
            return "active"
        if snap["armed"]:
            return "armed"
        if executable("Hyprland") or executable("hyprland"):
            return "ready"
        return "not_installed"

    def snapshot(self) -> dict[str, Any]:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        desktop_names = {name.strip().lower() for name in desktop.split(":") if name.strip()}
        raw = {
            "available": True,
            "hyprland_active": bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
            or "hyprland" in desktop_names,
            "cinnamon_active": any("cinnamon" in name for name in desktop_names),
            "armed": self._flag_path().is_file(),
            "desktop": desktop,
            "tty_hint": "Ctrl+Alt+F3",
            "arm_explanation": (
                "Prepare a one-time Hyprland launch after switching to a TTY. "
                "This does not log out or terminate Cinnamon."
            ),
        }
        raw["lifecycle"] = self._lifecycle_status(raw)
        raw["status"] = raw["lifecycle"]
        return envelope(
            self.id,
            raw,
            capabilities=("arm_once", "disarm", "status", "verify_configuration"),
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Keep arm_hyprland as a compatibility alias for arm_once.
        if name in {"status", "verify_configuration"}:
            snap = self.snapshot()
            return {"ok": True, **snap}
        if name in {"arm_once", "arm_hyprland"}:
            return self._arm()
        if name == "disarm":
            return self._disarm()
        return command_error("unavailable", f"unknown session command: {name}")

    def _arm(self) -> dict[str, Any]:
        flag = self._flag_path()
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch(exist_ok=True)
        except OSError as exc:
            return command_error("permission_denied", f"could not arm Hyprland one-shot: {exc}")
        return {
            "ok": True,
            "armed": True,
            "lifecycle": "armed",
            "flag": str(flag),
            "instructions": (
                "Press Ctrl+Alt+F3, then log in. "
                "This arms a one-shot TTY launch; it does not log out of Cinnamon."
            ),
        }

    def _disarm(self) -> dict[str, Any]:
        flag = self._flag_path()
        try:
            if flag.exists():
                flag.unlink()
        except OSError as exc:
            return command_error("permission_denied", f"could not disarm Hyprland one-shot: {exc}")
        return {"ok": True, "armed": False, "lifecycle": self._lifecycle_status({
            "hyprland_active": bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")),
            "armed": False,
        })}
