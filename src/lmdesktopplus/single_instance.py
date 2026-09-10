"""Single-instance guard for the LMDesktopPlus control center.

Uses an advisory ``flock`` on a lock file in the runtime directory. The lock is
held for the lifetime of the owning process and is released automatically by the
kernel if the process dies, so stale locks never block a relaunch.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path

from .util import APP_ID, app_cache_dir, ensure_private_dir, executable, spawn


def runtime_dir() -> Path:
    """Prefer ``$XDG_RUNTIME_DIR``; fall back to the app cache directory."""
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(xdg) if xdg else app_cache_dir()
    return ensure_private_dir(base / APP_ID)


class SingleInstance:
    """Best-effort single-instance lock.

    ``acquire()`` returns ``True`` for the first process and ``False`` when
    another live process already holds the lock.
    """

    def __init__(self, name: str = APP_ID) -> None:
        self.path = runtime_dir() / f"{name}.lock"
        self._fh = None

    def acquire(self) -> bool:
        fh = open(self.path, "a+")  # noqa: SIM115 — kept open for the process lifetime
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        self._fh = fh
        return True

    def owner_pid(self) -> int | None:
        try:
            text = self.path.read_text(encoding="utf-8").strip()
            return int(text) if text else None
        except (OSError, ValueError):
            return None

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "SingleInstance":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def focus_existing_window(wm_class: str = APP_ID) -> bool:
    """Best-effort raise of an already-running UI window by WM class.

    Returns ``True`` if a focus tool was invoked successfully. Silently reports
    ``False`` when no tool is available (e.g. headless or pure Wayland).
    """
    if executable("wmctrl"):
        # wmctrl matches against WM_CLASS "name.class"; try both spellings.
        for target in (f"{wm_class}.{wm_class}", wm_class):
            try:
                if spawn(["wmctrl", "-x", "-a", target]):
                    return True
            except OSError:
                continue
    if executable("xdotool"):
        try:
            if spawn(["xdotool", "search", "--class", wm_class, "windowactivate"]):
                return True
        except OSError:
            return False
    return False
