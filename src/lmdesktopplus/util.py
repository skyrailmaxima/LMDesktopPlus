from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

APP_ID = "lmdesktopplus"


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def xdg_cache_home() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def app_config_dir() -> Path:
    return xdg_config_home() / APP_ID


def app_data_dir() -> Path:
    return xdg_data_home() / APP_ID


def app_cache_dir() -> Path:
    return xdg_cache_home() / APP_ID


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def atomic_write_json(path: Path, value: Any) -> None:
    ensure_private_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def executable(name: str) -> str | None:
    return shutil.which(name)


def first_executable(names: Iterable[str]) -> str | None:
    for name in names:
        found = executable(name)
        if found:
            return found
    return None


def run_capture(argv: Sequence[str], timeout: float = 4.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env={**os.environ, "LC_ALL": "C.UTF-8"},
    )


def spawn(argv: Sequence[str], *, cwd: Path | None = None) -> int:
    proc = subprocess.Popen(
        list(argv),
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    return proc.pid


def safe_name(value: str) -> bool:
    return bool(value) and len(value) <= 64 and all(c.isalnum() or c in "-_." for c in value)
