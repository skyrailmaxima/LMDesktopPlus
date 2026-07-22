from __future__ import annotations

from typing import Any, Protocol


class Adapter(Protocol):
    id: str

    def available(self) -> bool: ...

    def snapshot(self) -> dict[str, Any]: ...

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class NullAdapter:
    def __init__(self, adapter_id: str) -> None:
        self.id = adapter_id

    def available(self) -> bool:
        return True

    def snapshot(self) -> dict[str, Any]:
        return {"available": self.available()}

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": f"{self.id} does not support commands"}
