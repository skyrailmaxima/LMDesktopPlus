from __future__ import annotations

import copy
import re
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

# Scenes that may carry user text/layout overrides. Mirrors the `scenes` array in
# static/app.js; unknown scenes are dropped on validation (fail-soft).
KNOWN_SCENES = (
    "desktop", "terminal", "tmux", "editor", "browser", "rofi",
    "docs", "monitor", "apps", "settings", "kit",
)
GREETING_MODES = ("static", "sequential", "random", "time")
TEXT_FIELDS = ("title", "subtitle")
# Bounds for user-editable customization (defensive caps; these are personal
# preferences, not security-sensitive, so validation is structural + bounded).
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_MAX_GREETINGS = 24
_MAX_TEXT_LEN = 120
_MAX_TEXT_ENTRIES = 64
_MAX_TILES = 32

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
        "idle_lock_minutes": 0,
        "idle_sleep_minutes": 0,
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
        "live_wallpaper": True,
    },
    # User personalization: editable greeting, scene text overrides, and per-scene
    # tile layouts. Defaults are inert so an untouched install renders as before.
    "customization": {
        "greeting": {
            "messages": ["VAPOR//MATRIX"],
            "mode": "static",
            "rotate_seconds": 0,
        },
        "text": {},
        "layouts": {},
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
        try:
            behavior["idle_lock_minutes"] = max(
                0, min(120, int(behavior.get("idle_lock_minutes", 0)))
            )
        except (TypeError, ValueError):
            behavior["idle_lock_minutes"] = 0
        try:
            behavior["idle_sleep_minutes"] = max(
                0, min(240, int(behavior.get("idle_sleep_minutes", 0)))
            )
        except (TypeError, ValueError):
            behavior["idle_sleep_minutes"] = 0
        result["features"] = {str(k): bool(v) for k, v in result.get("features", {}).items()}
        result["customization"] = SettingsStore._validate_customization(
            result.get("customization", {})
        )
        return result

    @staticmethod
    def _clean_str(value: Any, max_len: int = _MAX_TEXT_LEN) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        return text[:max_len]

    @staticmethod
    def _clean_slug_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and _SLUG_RE.match(item) and item not in out:
                out.append(item)
            if len(out) >= _MAX_TILES:
                break
        return out

    @staticmethod
    def _validate_customization(value: Any) -> dict[str, Any]:
        base = copy.deepcopy(DEFAULT_SETTINGS["customization"])
        if not isinstance(value, dict):
            return base

        # --- greeting -------------------------------------------------------
        greeting = value.get("greeting")
        if isinstance(greeting, dict):
            raw_messages = greeting.get("messages")
            messages: list[str] = []
            if isinstance(raw_messages, list):
                for item in raw_messages:
                    cleaned = SettingsStore._clean_str(item)
                    if cleaned is not None:
                        messages.append(cleaned)
                    if len(messages) >= _MAX_GREETINGS:
                        break
            base["greeting"]["messages"] = messages or ["VAPOR//MATRIX"]
            mode = greeting.get("mode")
            base["greeting"]["mode"] = mode if mode in GREETING_MODES else "static"
            try:
                secs = int(greeting.get("rotate_seconds", 0))
            except (TypeError, ValueError):
                secs = 0
            base["greeting"]["rotate_seconds"] = 0 if secs <= 0 else max(5, min(3600, secs))

        # --- text overrides -------------------------------------------------
        text = value.get("text")
        clean_text: dict[str, str] = {}
        if isinstance(text, dict):
            for key, val in text.items():
                if not isinstance(key, str) or "." not in key:
                    continue
                scene, _, field = key.partition(".")
                if scene not in KNOWN_SCENES or field not in TEXT_FIELDS:
                    continue
                cleaned = SettingsStore._clean_str(val)
                if cleaned is None:
                    continue
                clean_text[key] = cleaned
                if len(clean_text) >= _MAX_TEXT_ENTRIES:
                    break
        base["text"] = clean_text

        # --- per-scene tile layouts ----------------------------------------
        layouts = value.get("layouts")
        clean_layouts: dict[str, Any] = {}
        if isinstance(layouts, dict):
            for scene, layout in layouts.items():
                if scene not in KNOWN_SCENES or not isinstance(layout, dict):
                    continue
                entry: dict[str, Any] = {}
                order = SettingsStore._clean_slug_list(layout.get("order"))
                if order:
                    entry["order"] = order
                hidden = SettingsStore._clean_slug_list(layout.get("hidden"))
                if hidden:
                    entry["hidden"] = hidden
                views_raw = layout.get("views")
                if isinstance(views_raw, dict):
                    views: dict[str, str] = {}
                    for tile, view in views_raw.items():
                        if (
                            isinstance(tile, str) and _SLUG_RE.match(tile)
                            and isinstance(view, str) and _SLUG_RE.match(view)
                        ):
                            views[tile] = view
                        if len(views) >= _MAX_TILES:
                            break
                    if views:
                        entry["views"] = views
                if entry:
                    clean_layouts[scene] = entry
        base["layouts"] = clean_layouts
        return base
