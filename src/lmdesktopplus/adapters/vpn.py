"""VPN / WireGuard profiles via NetworkManager nmcli (Stage C).

@use levels: snapshot is medium use; up/down are low use. Never stores secrets.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..network import _split_nmcli
from ..preopt import Outcome, try_run
from ..util import executable
from .base import command_error, dispatch_command

_VPN_TYPES = frozenset({"vpn", "wireguard"})
_NAME_RE = re.compile(r"^[\w .@+()\[\]-]{1,128}$")


@register_fn(
    "vpn.normalize_connection_name",
    UseLevel.MEDIUM,
    "Validate nmcli connection name from UI payload",
)
def normalize_connection_name(value: Any) -> str | None:
    # @use: medium use — purpose: refuse shell-like VPN connection names
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or not _NAME_RE.match(name):
        return None
    return name


@register_fn(
    "vpn.parse_vpn_connections",
    UseLevel.MEDIUM,
    "Parse nmcli -t connection rows into VPN/WireGuard list",
)
def parse_vpn_connections(output: str, active_names: set[str] | None = None) -> list[dict[str, Any]]:
    # @use: medium use — purpose: Settings VPN panel rows from nmcli tabular output
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
    """List/up/down VPN profiles without persisting credentials."""

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
        # @use: medium use — purpose: Settings VPN panel poll
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        probed = self._probe_connections()
        snapshot = (
            probed.value
            if probed.ok
            else {"available": False, "last_error": probed.error}
        )
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_connections(self) -> Outcome:
        # @use: medium use — purpose: nmcli active+all list without raises
        active = self._nmcli_connections(active_only=True)
        if not active.ok:
            return active
        listed = self._nmcli_connections(active_only=False)
        if not listed.ok:
            return listed
        active_names = {row["name"] for row in parse_vpn_connections(active.value)}
        connections = parse_vpn_connections(listed.value, active_names)
        return Outcome.success(
            {
                "available": True,
                "backend": "nmcli",
                "connections": connections,
                "active_count": sum(1 for row in connections if row["active"]),
            }
        )

    def _nmcli_connections(self, *, active_only: bool) -> Outcome:
        # @use: medium use — purpose: one nmcli connection show (active or all)
        argv = [
            self.nmcli,
            "-t",
            "-f",
            "NAME,TYPE,DEVICE,STATE",
            "connection",
            "show",
            *(["--active"] if active_only else []),
        ]
        run = try_run(argv, timeout=4)
        label = "active connections" if active_only else "connections"
        return (
            Outcome.success(run.stdout)
            if run.ok
            else Outcome.fail(run.error or run.stderr.strip() or f"nmcli {label} failed")
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: VPN up/down/refresh via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "up": lambda payload: self._require_nmcli(lambda: self._connect_named("up", payload)),
            "down": lambda payload: self._require_nmcli(lambda: self._connect_named("down", payload)),
            "refresh": lambda _payload: self._require_nmcli(self._refresh),
        }

    def _require_nmcli(self, action):
        if not self.available():
            return command_error("unavailable", "nmcli is not installed")
        return action()

    def _refresh(self) -> dict[str, Any]:
        self._cached_snapshot = None
        return {"ok": True, **self.snapshot()}

    def _connect_named(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        connection = normalize_connection_name(payload.get("name") or payload.get("connection"))
        if connection is None:
            return command_error("invalid_argument", "connection name is invalid")
        return self._up_or_down(action, connection)

    def _up_or_down(self, action: str, connection: str) -> dict[str, Any]:
        # @use: low use — purpose: nmcli connection up/down for one named profile
        run = try_run([self.nmcli, "connection", action, connection], timeout=45)
        if not run.launched:
            return (
                command_error("timeout", f"nmcli connection {action} timed out")
                if "timed out" in run.error
                else command_error("internal_error", run.error)
            )
        if not run.ok:
            error = run.stderr.strip() or f"nmcli connection {action} failed"
            lower = error.lower()
            # Polkit denials surface as permission_denied for the UI chip.
            denied = (
                "permission" in lower
                or "not authorized" in lower
                or "polkit" in lower
            )
            return (
                command_error("permission_denied", error)
                if denied
                else command_error("internal_error", error)
            )
        self._cached_snapshot = None
        return {"ok": True, "action": action, "name": connection}
