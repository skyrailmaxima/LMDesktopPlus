"""Allowlisted desktop actions — preopt try_run / first_ok_scan on host edges.

@use levels: capabilities/launch are high/medium; lock/power are low.
Linux Mint remains the primary rice; FreeBSD ships the UI package with
sysctl-friendly lock/power argv and broader terminal candidates.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Callable

from .fncache import UseLevel, register_fn
from .platform_os import is_freebsd
from .preopt import Outcome, first_ok_scan, try_mkdir, try_run
from .util import app_config_dir, executable, first_executable, spawn

# kitty/gnome first for Mint; xterm/alacritty cover FreeBSD ports defaults.
TERMINAL_CANDIDATES = (
    "kitty",
    "alacritty",
    "gnome-terminal",
    "x-terminal-emulator",
    "xfce4-terminal",
    "mate-terminal",
    "xterm",
    "uxterm",
    "urxvt",
)

EDITOR_CANDIDATES = ("pulsar", "cursor", "codium", "code", "xed", "mousepad", "gedit")
BROWSER_CANDIDATES = (
    "firefox",
    "google-chrome",
    "chromium",
    "ungoogled-chromium",
    "chrome",
    "xdg-open",
)
FILE_MANAGER_CANDIDATES = ("nemo", "nautilus", "thunar", "caja", "pcmanfm", "xdg-open")
MONITOR_CANDIDATES = ("btop", "gnome-system-monitor", "htop", "top")
SETTINGS_CANDIDATES = (
    "cinnamon-settings",
    "gnome-control-center",
    "xfce4-settings-manager",
)


@register_fn(
    "actions.wrap_in_terminal",
    UseLevel.MEDIUM,
    "Wrap argv for preferred terminal (optional hold + working directory)",
)
def wrap_in_terminal(
    argv: list[str],
    *,
    hold: bool = False,
    directory: Path | str | None = None,
) -> list[str] | None:
    """Wrap argv for the preferred terminal using a name → builder map.

    @use: medium use — purpose: launch allowlisted actions / agent peers in a terminal.
    """
    terminal = first_executable(TERMINAL_CANDIDATES)
    if not terminal:
        return None
    base = Path(terminal).name
    workdir = str(directory) if directory is not None else None

    def kitty() -> list[str]:
        prefix = [terminal]
        if workdir:
            prefix += ["--directory", workdir]
        if hold:
            prefix.append("--hold")
        return [*prefix, *argv]

    def gnome() -> list[str]:
        prefix = [terminal]
        if workdir:
            prefix.append(f"--working-directory={workdir}")
        return [*prefix, "--", *argv]

    def xfce() -> list[str]:
        prefix = [terminal]
        if workdir:
            prefix.append(f"--working-directory={workdir}")
        joined = shlex.join(argv)
        if hold:
            return [*prefix, "--hold", "--command", joined]
        return [*prefix, "--command", joined]

    def alacritty() -> list[str]:
        prefix = [terminal]
        if workdir:
            prefix += ["--working-directory", workdir]
        if hold:
            # alacritty has no --hold; leave process attached via shell.
            return [*prefix, "-e", "sh", "-c", f"{shlex.join(argv)}; echo; read -r _"]
        return [*prefix, "-e", *argv]

    def default() -> list[str]:
        if len(argv) == 1 and not hold:
            return [terminal, "-e", argv[0]]
        return [terminal, "-e", shlex.join(argv)]

    wrappers: dict[str, Callable[[], list[str]]] = {
        "kitty": kitty,
        "gnome-terminal": gnome,
        "mate-terminal": gnome,
        "xfce4-terminal": xfce,
        "alacritty": alacritty,
    }
    return wrappers.get(base, default)()


def _lock_candidates() -> list[list[str]]:
    # @use: low use — purpose: Linux + FreeBSD lock argv etch (first success wins)
    argv_table: tuple[list[str], ...] = (
        ["loginctl", "lock-session"],
        ["cinnamon-screensaver-command", "--lock"],
        ["xdg-screensaver", "lock"],
        ["xscreensaver-command", "-lock"],
        ["xlock"],
        ["swaylock"],
        ["i3lock"],
    )
    return [argv for argv in argv_table if executable(argv[0])]


def _power_argv(action: str) -> list[str] | None:
    # @use: low use — purpose: OS-specific allowlisted power command
    uid = str(os.getuid())
    if is_freebsd():
        freebsd_map: dict[str, list[str]] = {
            "logout": ["loginctl", "terminate-user", uid],
            "suspend": ["zzz"] if executable("zzz") else ["acpiconf", "-s", "3"],
            "reboot": ["shutdown", "-r", "now"],
            "poweroff": ["shutdown", "-p", "now"],
        }
        argv = freebsd_map.get(action)
        if argv is None:
            return None
        # FreeBSD logout without elogind/loginctl: soft fail at spawn time.
        if action == "logout" and not executable("loginctl"):
            return None
        return argv
    linux_map = {
        "logout": ["loginctl", "terminate-user", uid],
        "suspend": ["systemctl", "suspend"],
        "reboot": ["systemctl", "reboot"],
        "poweroff": ["systemctl", "poweroff"],
    }
    return linux_map.get(action)


class ActionRunner:
    def __init__(self, settings_getter) -> None:
        self.settings_getter = settings_getter

    @staticmethod
    def capabilities() -> dict[str, Any]:
        apps = {
            "terminal": first_executable(TERMINAL_CANDIDATES),
            "editor": first_executable(EDITOR_CANDIDATES),
            "browser": first_executable(BROWSER_CANDIDATES),
            "monitor": first_executable(MONITOR_CANDIDATES),
            "rofi": executable("rofi"),
            "settings": first_executable(SETTINGS_CANDIDATES),
            "file_manager": first_executable(FILE_MANAGER_CANDIDATES),
            "tmux": executable("tmux"),
            "hyprctl": executable("hyprctl"),
            "nmcli": executable("nmcli"),
            "playerctl": executable("playerctl"),
            "audio": first_executable(["wpctl", "pactl", "mixer"]),
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
        cmd = first_executable(EDITOR_CANDIDATES)
        if not cmd:
            return {"ok": False, "error": "no supported editor found"}
        return {"ok": True, "pid": spawn([cmd, str(Path.home() / "work")])}

    @staticmethod
    def _browser() -> dict[str, Any]:
        cmd = first_executable(BROWSER_CANDIDATES)
        if not cmd:
            return {"ok": False, "error": "no browser found"}
        return {"ok": True, "pid": spawn([cmd, "about:blank"])}

    @staticmethod
    def _monitor() -> dict[str, Any]:
        gui = executable("gnome-system-monitor")
        if gui:
            return {"ok": True, "pid": spawn([gui])}
        btop = first_executable(["btop", "htop", "top"])
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
        cmd = first_executable(SETTINGS_CANDIDATES)
        if not cmd:
            return {"ok": False, "error": "desktop settings application not found"}
        return {"ok": True, "pid": spawn([cmd])}

    @staticmethod
    def open_path(path: Path) -> dict[str, Any]:
        # @use: low use — purpose: open-config / files; mkdir soft
        path = path.expanduser()
        made = try_mkdir(path)
        if not made.ok:
            return {"ok": False, "error": made.error or "could not create path"}
        cmd = first_executable(FILE_MANAGER_CANDIDATES)
        if not cmd:
            return {"ok": False, "error": "file manager not found"}
        try:
            return {"ok": True, "pid": spawn([cmd, str(path)])}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def lock() -> dict[str, Any]:
        # @use: low use — purpose: lock-session via first_ok_scan + try_run
        candidates = _lock_candidates()

        def probe(argv: list[str]) -> Outcome:
            run = try_run(argv, timeout=5)
            return (
                Outcome.success(argv[0])
                if run.ok
                else Outcome.fail(run.error or run.stderr.strip() or argv[0])
            )

        result = first_ok_scan(
            candidates,
            probe,
            empty_error="no lock command succeeded",
        )
        return (
            {"ok": True, "method": result.value}
            if result.ok
            else {"ok": False, "error": result.error}
        )

    def power(self, action: str) -> dict[str, Any]:
        settings = self.settings_getter()
        if not settings.get("behavior", {}).get("allow_power_actions", False):
            return {"ok": False, "error": "power actions are disabled in LMDesktopPlus settings"}
        argv = _power_argv(action)
        if argv is None:
            return {"ok": False, "error": f"no power backend for {action}"}
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
