from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Any

from .util import app_config_dir, executable, first_executable, run_capture, spawn


class ActionRunner:
    def __init__(self, settings_getter) -> None:
        self.settings_getter = settings_getter

    @staticmethod
    def capabilities() -> dict[str, Any]:
        apps = {
            "terminal": first_executable(["kitty", "gnome-terminal", "x-terminal-emulator", "xfce4-terminal"]),
            "editor": first_executable(["pulsar", "cursor", "codium", "code", "xed"]),
            "browser": first_executable(["firefox", "google-chrome", "chromium", "xdg-open"]),
            "monitor": first_executable(["btop", "gnome-system-monitor", "htop"]),
            "rofi": executable("rofi"),
            "settings": first_executable(["cinnamon-settings", "gnome-control-center"]),
            "file_manager": first_executable(["nemo", "nautilus", "thunar", "xdg-open"]),
            "tmux": executable("tmux"),
            "hyprctl": executable("hyprctl"),
            "nmcli": executable("nmcli"),
            "playerctl": executable("playerctl"),
            "bubblewrap": executable("bwrap"),
        }
        return {key: {"available": bool(value), "path": value} for key, value in apps.items()}

    def run(self, action: str, target: str | None = None) -> dict[str, Any]:
        if action == "launch":
            return self.launch(target or "")
        if action == "lock":
            return self.lock()
        if action in {"logout", "suspend", "reboot", "poweroff"}:
            return self.power(action)
        if action == "open-config":
            return self.open_path(app_config_dir())
        return {"ok": False, "error": "unsupported action"}

    def launch(self, target: str) -> dict[str, Any]:
        handlers = {
            "terminal": self._terminal,
            "tmux": self._tmux,
            "editor": self._editor,
            "browser": self._browser,
            "rofi": self._rofi,
            "docs": lambda: self.open_path(Path.home() / ".config"),
            "monitor": self._monitor,
            "settings": self._settings,
            "files": lambda: self.open_path(Path.home()),
        }
        handler = handlers.get(target)
        if not handler:
            return {"ok": False, "error": f"unknown launch target: {target}"}
        try:
            return handler()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _terminal() -> dict[str, Any]:
        cmd = first_executable(["kitty", "gnome-terminal", "x-terminal-emulator", "xfce4-terminal"])
        if not cmd:
            return {"ok": False, "error": "no terminal emulator found"}
        return {"ok": True, "pid": spawn([cmd])}

    @staticmethod
    def _tmux() -> dict[str, Any]:
        tmux = executable("tmux")
        terminal = first_executable(["kitty", "gnome-terminal", "x-terminal-emulator", "xfce4-terminal"])
        if not tmux or not terminal:
            return {"ok": False, "error": "tmux or a supported terminal is missing"}
        argv = [tmux, "new-session", "-A", "-s", "lmdesktopplus"]
        base = Path(terminal).name
        if base == "kitty":
            cmd = [terminal, "--hold", *argv]
        elif base == "gnome-terminal":
            cmd = [terminal, "--", *argv]
        elif base == "xfce4-terminal":
            cmd = [terminal, "--hold", "--command", shlex.join(argv)]
        else:
            cmd = [terminal, "-e", shlex.join(argv)]
        return {"ok": True, "pid": spawn(cmd)}

    @staticmethod
    def _editor() -> dict[str, Any]:
        cmd = first_executable(["pulsar", "cursor", "codium", "code", "xed"])
        if not cmd:
            return {"ok": False, "error": "no supported editor found"}
        return {"ok": True, "pid": spawn([cmd, str(Path.home() / "work")])}

    @staticmethod
    def _browser() -> dict[str, Any]:
        cmd = first_executable(["firefox", "google-chrome", "chromium", "xdg-open"])
        if not cmd:
            return {"ok": False, "error": "no browser found"}
        return {"ok": True, "pid": spawn([cmd, "about:blank"])}

    @staticmethod
    def _monitor() -> dict[str, Any]:
        gui = executable("gnome-system-monitor")
        if gui:
            return {"ok": True, "pid": spawn([gui])}
        btop = executable("btop") or executable("htop")
        terminal = first_executable(["kitty", "gnome-terminal", "x-terminal-emulator", "xfce4-terminal"])
        if not btop or not terminal:
            return {"ok": False, "error": "no supported system monitor found"}
        base = Path(terminal).name
        if base == "kitty":
            cmd = [terminal, "--hold", btop]
        elif base == "gnome-terminal":
            cmd = [terminal, "--", btop]
        else:
            cmd = [terminal, "-e", btop]
        return {"ok": True, "pid": spawn(cmd)}

    @staticmethod
    def _rofi() -> dict[str, Any]:
        rofi = executable("rofi")
        if not rofi:
            return {"ok": False, "error": "rofi is not installed"}
        return {"ok": True, "pid": spawn([rofi, "-show", "drun"])}

    @staticmethod
    def _settings() -> dict[str, Any]:
        cmd = first_executable(["cinnamon-settings", "gnome-control-center"])
        if not cmd:
            return {"ok": False, "error": "desktop settings application not found"}
        return {"ok": True, "pid": spawn([cmd])}

    @staticmethod
    def open_path(path: Path) -> dict[str, Any]:
        path = path.expanduser()
        path.mkdir(parents=True, exist_ok=True)
        cmd = first_executable(["nemo", "nautilus", "thunar", "xdg-open"])
        if not cmd:
            return {"ok": False, "error": "file manager not found"}
        return {"ok": True, "pid": spawn([cmd, str(path)])}

    @staticmethod
    def lock() -> dict[str, Any]:
        commands = [
            ["loginctl", "lock-session"],
            ["cinnamon-screensaver-command", "--lock"],
            ["xdg-screensaver", "lock"],
        ]
        errors = []
        for argv in commands:
            if not executable(argv[0]):
                continue
            cp = run_capture(argv, timeout=5)
            if cp.returncode == 0:
                return {"ok": True, "method": argv[0]}
            errors.append(cp.stderr.strip())
        return {"ok": False, "error": "; ".join(x for x in errors if x) or "no lock command succeeded"}

    def power(self, action: str) -> dict[str, Any]:
        settings = self.settings_getter()
        if not settings.get("behavior", {}).get("allow_power_actions", False):
            return {"ok": False, "error": "power actions are disabled in LMDesktopPlus settings"}
        mapping = {
            "logout": ["loginctl", "terminate-user", str(os.getuid())],
            "suspend": ["systemctl", "suspend"],
            "reboot": ["systemctl", "reboot"],
            "poweroff": ["systemctl", "poweroff"],
        }
        argv = mapping[action]
        if not executable(argv[0]):
            return {"ok": False, "error": f"{argv[0]} is unavailable"}
        try:
            return {"ok": True, "pid": spawn(argv), "action": action}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
