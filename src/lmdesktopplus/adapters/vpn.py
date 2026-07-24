from __future__ import annotations

import re
import subprocess
import time
from typing import Any

from ..network import _split_nmcli
from ..util import executable, run_capture
from .base import command_error

_VPN_TYPES = frozenset({"vpn", "wireguard"})
_NAME_RE = re.compile(r"^[\w .@+()\[\]-]{1,128}$")


def normalize_connection_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or not _NAME_RE.match(name):
        return None
    return name


def parse_vpn_connections(output: str, active_names: set[str] | None = None) -> list[dict[str, Any]]:
    active = active_names or set()
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = _split_nmcli(line)
        if len(parts) < 4:
            continue
        name, conn_type, device, state = parts[0], parts[1], parts[2], parts[3]
        type_base = conn_type.split(":")[0].lower() if conn_type else ""
        if type_base not in _VPN_TYPES:
            continue
        rows.append(
            {
                "name": name,
                "type": type_base,
                "device": device or None,
                "state": state,
                "active": name in active or state.lower() in {"activated", "activating"},
            }
        )
    rows.sort(key=lambda row: (not row["active"], row["name"].lower()))
    return rows


class VpnAdapter:
    id = "vpn"

    def __init__(self, cache_ttl: float = 5.0, nmcli: str | None = None) -> None:
        if nmcli is None:
            nmcli = executable("nmcli")
        self.nmcli = nmcli or None
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.nmcli)

    def snapshot(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            active_cp = run_capture(
                [
                    self.nmcli,
                    "-t",
                    "-f",
                    "NAME,TYPE,DEVICE,STATE",
                    "connection",
                    "show",
                    "--active",
                ],
                timeout=4,
            )
            if active_cp.returncode != 0:
                raise RuntimeError(active_cp.stderr.strip() or "nmcli active connections failed")
            active_names = {
                row["name"]
                for row in parse_vpn_connections(active_cp.stdout)
            }
            all_cp = run_capture(
                [
                    self.nmcli,
                    "-t",
                    "-f",
                    "NAME,TYPE,DEVICE,STATE",
                    "connection",
                    "show",
                ],
                timeout=4,
            )
            if all_cp.returncode != 0:
                raise RuntimeError(all_cp.stderr.strip() or "nmcli connections failed")
            connections = parse_vpn_connections(all_cp.stdout, active_names)
            snapshot = {
                "available": True,
                "backend": "nmcli",
                "connections": connections,
                "active_count": sum(1 for row in connections if row["active"]),
            }
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            snapshot = {"available": False, "last_error": str(exc)}
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in {"up", "down", "refresh"}:
            return command_error("unavailable", f"unknown vpn command: {name}")
        if not self.available():
            return command_error("unavailable", "nmcli is not installed")
        if name == "refresh":
            self._cached_snapshot = None
            return {"ok": True, **self.snapshot()}
        connection = normalize_connection_name(payload.get("name") or payload.get("connection"))
        if connection is None:
            return command_error("invalid_argument", "connection name is invalid")
        return self._up_or_down(name, connection)

    def _up_or_down(self, action: str, connection: str) -> dict[str, Any]:
        try:
            result = run_capture(
                [self.nmcli, "connection", action, connection],
                timeout=45,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                return command_error("timeout", f"nmcli connection {action} timed out")
            return command_error("internal_error", str(exc))
        if result.returncode != 0:
            error = result.stderr.strip() or f"nmcli connection {action} failed"
            lower = error.lower()
            if "permission" in lower or "not authorized" in lower or "polkit" in lower:
                return command_error("permission_denied", error)
            return command_error("internal_error", error)
        self._cached_snapshot = None
        return {"ok": True, "action": action, "name": connection}
