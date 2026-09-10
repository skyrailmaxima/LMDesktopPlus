"""Persisted UI shell state (window geometry + last active scene).

This is deliberately separate from :mod:`lmdesktopplus.config`: settings are
user-facing, validated preferences, whereas this store holds transient shell
state that the native window restores on the next launch. It fails soft — a
missing or corrupt file simply yields the defaults.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from .util import app_data_dir, atomic_write_json, read_json

DEFAULT_SCENE = "desktop"
MIN_WIDTH = 640
MIN_HEIGHT = 480
DEFAULT_WIDTH = 1320
DEFAULT_HEIGHT = 840

# Scene ids are short, lowercase slugs defined by the frontend. Anything else is
# rejected so a stray write can never smuggle unexpected content into the file.
_SCENE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

DEFAULT_UI_STATE: dict[str, Any] = {
    "scene": DEFAULT_SCENE,
    "window": {
        "width": DEFAULT_WIDTH,
        "height": DEFAULT_HEIGHT,
        "maximized": False,
    },
}


def valid_scene(value: Any) -> bool:
    return isinstance(value, str) and bool(_SCENE_RE.match(value))


class UiStateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "ui-state.json"
        self._lock = threading.RLock()
        loaded = read_json(self.path, {})
        self._value = self._normalize(loaded if isinstance(loaded, dict) else {})

    def get(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scene": self._value["scene"],
                "window": dict(self._value["window"]),
            }

    def scene(self) -> str:
        with self._lock:
            return self._value["scene"]

    def set_scene(self, scene: str) -> str:
        with self._lock:
            if valid_scene(scene):
                self._value["scene"] = scene
                self._save()
            return self._value["scene"]

    def set_window(self, width: int, height: int, maximized: bool) -> dict[str, Any]:
        with self._lock:
            self._value["window"] = self._normalize_window(
                {"width": width, "height": height, "maximized": maximized}
            )
            self._save()
            return dict(self._value["window"])

    def _save(self) -> None:
        atomic_write_json(self.path, self._value)

    @classmethod
    def _normalize(cls, value: dict[str, Any]) -> dict[str, Any]:
        scene = value.get("scene")
        window = value.get("window") if isinstance(value.get("window"), dict) else {}
        return {
            "scene": scene if valid_scene(scene) else DEFAULT_SCENE,
            "window": cls._normalize_window(window),
        }

    @staticmethod
    def _normalize_window(window: dict[str, Any]) -> dict[str, Any]:
        def _int(key: str, default: int, minimum: int) -> int:
            try:
                return max(minimum, int(window.get(key, default)))
            except (TypeError, ValueError):
                return default

        return {
            "width": _int("width", DEFAULT_WIDTH, MIN_WIDTH),
            "height": _int("height", DEFAULT_HEIGHT, MIN_HEIGHT),
            "maximized": bool(window.get("maximized", False)),
        }
