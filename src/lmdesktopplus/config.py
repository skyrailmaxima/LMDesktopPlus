from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

from .util import app_config_dir, atomic_write_json, read_json

ACCENTS = {
    "mag": "#ff2e97",
    "pink": "#ff71ce",
    "cyan": "#01cdfe",
    "mint": "#05ffa1",
    "purple": "#b967ff",
    "green": "#00ff70",
    "amber": "#ffcc44",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "appearance": {
        "accent": "mag",
        "font": "JetBrains Mono",
        "opacity": 90,
        "blur": 9,
        "rain_intensity": 55,
        "scanlines": True,
        "window_mode": "tiled",
        "surface": "blur",
        "gaps": True,
        "rounded": False,
        "shadows": True,
    },
    "behavior": {
        "start_fullscreen": False,
        "show_hints": True,
        "poll_interval_ms": 1000,
        "allow_power_actions": False,
        "do_not_disturb": False,
    },
    "features": {
        "claude": True,
        "cursor": True,
        "aider": True,
        "cody": False,
        "rust": True,
        "minimap": True,
        "gitn": True,
        "vapor": True,
        "kitty": True,
        "tmux": True,
        "waybar": True,
        "rofi": True,
        "starship": True,
        "hyprland": False,
        "bluetooth": True,
    },
}


def deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_config_dir() / "settings.json"
        self._lock = threading.RLock()
        loaded = read_json(self.path, {})
        self._value = self._validate(deep_merge(DEFAULT_SETTINGS, loaded if isinstance(loaded, dict) else {}))
        self.save()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._value)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            merged = deep_merge(self._value, patch)
            self._value = self._validate(merged)
            self.save()
            return copy.deepcopy(self._value)

    def save(self) -> None:
        atomic_write_json(self.path, self._value)

    @staticmethod
    def _validate(value: dict[str, Any]) -> dict[str, Any]:
        result = deep_merge(DEFAULT_SETTINGS, value)
        ap = result["appearance"]
        if ap.get("accent") not in ACCENTS:
            ap["accent"] = "mag"
        if ap.get("font") not in {"JetBrains Mono", "DotGothic16", "Zen Dots", "System UI"}:
            ap["font"] = "JetBrains Mono"
        ap["opacity"] = max(40, min(100, int(ap.get("opacity", 90))))
        ap["blur"] = max(0, min(24, int(ap.get("blur", 9))))
        ap["rain_intensity"] = max(0, min(100, int(ap.get("rain_intensity", 55))))
        ap["window_mode"] = ap.get("window_mode") if ap.get("window_mode") in {"tiled", "floating", "tabbed"} else "tiled"
        ap["surface"] = ap.get("surface") if ap.get("surface") in {"blur", "opaque", "acrylic"} else "blur"
        for key in ("scanlines", "gaps", "rounded", "shadows"):
            ap[key] = bool(ap.get(key, DEFAULT_SETTINGS["appearance"][key]))
        behavior = result["behavior"]
        behavior["start_fullscreen"] = bool(behavior.get("start_fullscreen", False))
        behavior["show_hints"] = bool(behavior.get("show_hints", True))
        behavior["allow_power_actions"] = bool(behavior.get("allow_power_actions", False))
        behavior["do_not_disturb"] = bool(behavior.get("do_not_disturb", False))
        behavior["poll_interval_ms"] = max(500, min(10000, int(behavior.get("poll_interval_ms", 1000))))
        result["features"] = {str(k): bool(v) for k, v in result.get("features", {}).items()}
        return result
