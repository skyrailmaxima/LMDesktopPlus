from __future__ import annotations

from typing import Any

from .base import Adapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> Adapter:
        return self._adapters[adapter_id]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            adapter_id: adapter.snapshot()
            for adapter_id, adapter in self._adapters.items()
        }
