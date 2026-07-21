from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Callable

from .adapters.wallpaper import WallpaperAdapter


def _load_icon_map() -> dict[str, dict[str, Any]]:
    manifest = files("lmdesktopplus").joinpath("static", "icons", "manifest.json")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: value
        for key, value in data.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


ICON_MAP: dict[str, dict[str, Any]] = _load_icon_map()
WALLPAPER_MAP: dict[str, dict[str, Any]] = WallpaperAdapter().wallpaper_map()


class AssetCatalog:
    def __init__(
        self,
        wallpaper_provider: Callable[[], dict[str, dict[str, Any]]] | None = None,
    ) -> None:
        self._wallpaper_provider = wallpaper_provider

    def as_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        wallpapers = (
            self._wallpaper_provider()
            if self._wallpaper_provider is not None
            else WALLPAPER_MAP.copy()
        )
        return {"icons": ICON_MAP.copy(), "wallpapers": wallpapers}
