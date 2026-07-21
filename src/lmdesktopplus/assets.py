from __future__ import annotations

from typing import Any


ICON_MAP: dict[str, dict[str, Any]] = {}


class AssetCatalog:
    def as_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"icons": ICON_MAP.copy()}
