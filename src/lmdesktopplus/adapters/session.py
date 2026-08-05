"""Hyprland one-shot arm / disarm for TTY handoff (Stage A).

Preoptimized: lifecycle status table + ternary chip; file I/O stays local OSError.
@use levels: snapshot is high use (desktop session chip); arm/disarm are low use.
Arming writes only a flag under app data — never logs out of Cinnamon.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..util import app_data_dir, executable
from .base import command_error, dispatch_command, envelope

# Ordered lifecycle gates — first matching predicate wins.
_LIFECYCLE_GATES: tuple[tuple[str, str], ...] = (
    ("hyprland_active", "active"),
    ("armed", "armed"),
)


class SessionAdapter:
    """Report desktop session + arm one-time Hyprland TTY launch."""

    id = "session"

    @staticmethod
    def _flag_path() -> Path:
        return app_data_dir() / "start-hyprland-once"

    def available(self) -> bool:
        return True

    def _lifecycle_status(self, snap: dict[str, Any]) -> str:
        # @use: high use — purpose: map session flags → lifecycle chip status
        for key, status in _LIFECYCLE_GATES:
            if snap.get(key):
                return status
        return (
            "ready"
            if executable("Hyprland") or executable("hyprland")
            else "not_installed"
        )

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: Desktop session / Hyprland arm chip
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
            capabilities=(
                "arm_once",
                "arm_hyprland",
                "disarm",
                "status",
                "verify_configuration",
            ),
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: session status/arm/disarm via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        # Keep arm_hyprland as a compatibility alias for arm_once.
        return {
            "status": self._status,
            "verify_configuration": self._status,
            "arm_once": lambda _payload: self._arm(),
            "arm_hyprland": lambda _payload: self._arm(),
            "disarm": lambda _payload: self._disarm(),
        }

    def _status(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: return enveloped session snapshot
        snap = self.snapshot()
        return {"ok": True, **snap}

    def _arm(self) -> dict[str, Any]:
        # @use: low use — purpose: touch one-shot Hyprland TTY flag only
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
        # @use: low use — purpose: remove one-shot Hyprland TTY flag
        flag = self._flag_path()
        try:
            if flag.exists():
                flag.unlink()
        except OSError as exc:
            return command_error("permission_denied", f"could not disarm Hyprland one-shot: {exc}")
        return {
            "ok": True,
            "armed": False,
            "lifecycle": self._lifecycle_status(
                {
                    "hyprland_active": bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")),
                    "armed": False,
                }
            ),
        }
