from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Callable

from .util import app_config_dir, executable, first_executable, run_capture, spawn

TERMINAL_CANDIDATES = ("kitty", "gnome-terminal", "x-terminal-emulator", "xfce4-terminal")


def wrap_in_terminal(argv: list[str], *, hold: bool = False) -> list[str] | None:
    """Wrap argv for the preferred terminal using a name → builder map.

    @use: medium use — purpose: launch allowlisted actions inside a terminal.
    """
    terminal = first_executable(TERMINAL_CANDIDATES)
    if not terminal:
        return None
    base = Path(terminal).name

    def kitty() -> list[str]:
        return [terminal, *(["--hold"] if hold else []), *argv]

    def gnome() -> list[str]:
        return [terminal, "--", *argv]

    def xfce() -> list[str]:
        joined = shlex.join(argv)
        if hold:
            return [terminal, "--hold", "--command", joined]
        return [terminal, "--command", joined]

    def default() -> list[str]:
        if len(argv) == 1 and not hold:
            return [terminal, "-e", argv[0]]
        return [terminal, "-e", shlex.join(argv)]

    wrappers: dict[str, Callable[[], list[str]]] = {
        "kitty": kitty,
        "gnome-terminal": gnome,
        "xfce4-terminal": xfce,
    }
    return wrappers.get(base, default)()


class ActionRunner:
    def __init__(self, settings_getter) -> None:
        self.settings_getter = settings_getter

    @staticmethod
    def capabilities() -> dict[str, Any]:
        apps = {
            "terminal": first_executable(TERMINAL_CANDIDATES),
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
            "audio": first_executable(["wpctl", "pactl"]),
            "bubblewrap": executable("bwrap"),
        }
        return {key: {"available": bool(value), "path": value} for key, value in apps.items()}

    def run(self, action: str, target: str | None = None) -> dict[str, Any]:
        handler = ACTION_HANDLERS.get(action)
        if handler is None:
            return {"ok": False, "error": "unsupported action"}
        return handler(self, target)

    def launch(self, target: str) -> dict[str, Any]:
        handler = LAUNCH_HANDLERS.get(target)
        if not handler:
            return {"ok": False, "error": f"unknown launch target: {target}"}
        try:
            return handler(self)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _terminal() -> dict[str, Any]:
        cmd = first_executable(TERMINAL_CANDIDATES)
        if not cmd:
            return {"ok": False, "error": "no terminal emulator found"}
        return {"ok": True, "pid": spawn([cmd])}

    @staticmethod
    def _tmux() -> dict[str, Any]:
        tmux = executable("tmux")
        if not tmux:
            return {"ok": False, "error": "tmux or a supported terminal is missing"}
        wrapped = wrap_in_terminal(
            [tmux, "new-session", "-A", "-s", "lmdesktopplus"],
            hold=True,
        )
        if not wrapped:
            return {"ok": False, "error": "tmux or a supported terminal is missing"}
        return {"ok": True, "pid": spawn(wrapped)}

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
        if not btop:
            return {"ok": False, "error": "no supported system monitor found"}
        wrapped = wrap_in_terminal([btop], hold=True)
        if not wrapped:
            return {"ok": False, "error": "no supported system monitor found"}
        return {"ok": True, "pid": spawn(wrapped)}

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


# Module-level dispatch tables so ActionRunner.run/launch stay branch-free.
ACTION_HANDLERS: dict[str, Callable[[ActionRunner, str | None], dict[str, Any]]] = {
    "launch": lambda runner, target: runner.launch(target or ""),
    "lock": lambda runner, _target: runner.lock(),
    "logout": lambda runner, _target: runner.power("logout"),
    "suspend": lambda runner, _target: runner.power("suspend"),
    "reboot": lambda runner, _target: runner.power("reboot"),
    "poweroff": lambda runner, _target: runner.power("poweroff"),
    "open-config": lambda runner, _target: runner.open_path(app_config_dir()),
}

LAUNCH_HANDLERS: dict[str, Callable[[ActionRunner], dict[str, Any]]] = {
    "terminal": lambda _runner: ActionRunner._terminal(),
    "tmux": lambda _runner: ActionRunner._tmux(),
    "editor": lambda _runner: ActionRunner._editor(),
    "browser": lambda _runner: ActionRunner._browser(),
    "rofi": lambda _runner: ActionRunner._rofi(),
    "docs": lambda runner: runner.open_path(Path.home() / ".config"),
    "monitor": lambda _runner: ActionRunner._monitor(),
    "settings": lambda _runner: ActionRunner._settings(),
    "files": lambda runner: runner.open_path(Path.home()),
}
