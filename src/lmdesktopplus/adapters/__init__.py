from __future__ import annotations

from typing import Any

from .base import Adapter, envelope


# Declared command capabilities for envelope metadata (authoritative for UI/docs).
ADAPTER_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "audio": ("set_volume", "toggle_mute"),
    "display": ("set_brightness",),
    "session": ("arm_once", "arm_hyprland", "disarm", "status", "verify_configuration"),
    "wallpaper": ("list", "apply"),
    "bluetooth": ("power", "scan", "connect", "disconnect"),
    "notifications": ("send_test", "set_dnd"),
    "updates": ("refresh", "open"),
    "clipboard": ("peek", "copy", "clear", "history"),
    "capture": ("full", "region", "open_folder"),
    "vpn": ("up", "down", "refresh"),
    "storage": ("mount", "unmount", "refresh"),
    "processes": ("refresh", "terminate"),
    "keybinds": ("scan", "tune", "melt", "synth"),
    "vault": ("scan", "probe", "install", "forge_pack"),
    "idle": ("status", "apply"),
    "printers": ("refresh", "open"),
    "logs": ("refresh",),
    "live_wallpaper": ("status", "start", "stop", "pulse_on", "pulse_off"),
}


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> Adapter:
        return self._adapters[adapter_id]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        from .base import classify_exception

        out: dict[str, dict[str, Any]] = {}
        for adapter_id, adapter in self._adapters.items():
            caps = ADAPTER_CAPABILITIES.get(adapter_id, ())
            try:
                snap = adapter.snapshot()
            except Exception as exc:  # noqa: BLE001 — snapshot boundary
                code, message = classify_exception(exc)
                out[adapter_id] = envelope(
                    adapter_id,
                    {
                        "available": False,
                        "status": "error",
                        "error": message,
                        "error_code": code,
                    },
                    capabilities=caps,
                )
                continue
            if (
                isinstance(snap, dict)
                and snap.get("id") == adapter_id
                and "status" in snap
                and "capabilities" in snap
            ):
                out[adapter_id] = snap
            elif isinstance(snap, dict):
                out[adapter_id] = envelope(adapter_id, snap, capabilities=caps)
            else:
                out[adapter_id] = envelope(
                    adapter_id, {"available": True, "value": snap}, capabilities=caps
                )
        return out
