from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


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


class AssetCatalog:
    def as_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"icons": ICON_MAP.copy()}
