"""NetworkManager helpers — preopt try_run on all nmcli edges.

@use levels: current is high (core poll); scan/connect/disconnect are medium/low.
"""

from __future__ import annotations

from typing import Any

from .fncache import UseLevel, register_fn
from .preopt import parse_int, try_run
from .util import executable


def _split_nmcli(line: str) -> list[str]:
    """Split nmcli's terse output without breaking escaped colons."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields


def available() -> bool:
    return executable("nmcli") is not None


@register_fn(
    "network.parse_active_connections",
    UseLevel.HIGH,
    "Parse nmcli active connection rows (one loop)",
)
def _parse_active_connections(output: str) -> list[dict[str, Any]]:
    # @use: high use — purpose: core network snapshot connection list
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = _split_nmcli(line)
        if len(parts) == 4:
            rows.append(
                {
                    "name": parts[0],
                    "type": parts[1],
                    "device": parts[2],
                    "state": parts[3],
                }
            )
    return rows


def current() -> dict[str, Any]:
    # @use: high use — purpose: Desktop/network poll; never raise on nmcli timeout
    if not available():
        return {"available": False, "connections": []}
    run = try_run(
        ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show", "--active"],
        timeout=4,
    )
    if not run.launched:
        return {"available": False, "connections": [], "last_error": run.error}
    rows = _parse_active_connections(run.stdout) if run.ok else []
    return {"available": True, "connections": rows}


@register_fn(
    "network.parse_wifi_list",
    UseLevel.MEDIUM,
    "Parse nmcli wifi list rows (one loop)",
)
def _parse_wifi_list(output: str) -> list[dict[str, Any]]:
    # @use: medium use — purpose: Wi-Fi scan panel rows
    networks: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = _split_nmcli(line)
        if len(parts) < 7:
            continue
        in_use, ssid, security, signal, freq, chan, device = parts[:7]
        if not ssid:
            continue
        signal_i = parse_int(signal) or 0
        networks.append(
            {
                "active": in_use.strip() == "*",
                "ssid": ssid,
                "security": security or "open",
                "signal": signal_i,
                "frequency": freq,
                "channel": chan,
                "device": device,
            }
        )
    networks.sort(key=lambda row: (not row["active"], -row["signal"], row["ssid"].lower()))
    return networks


def scan_wifi(rescan: bool = False) -> dict[str, Any]:
    # @use: medium use — purpose: Wi-Fi scan command
    if not available():
        return {"available": False, "networks": [], "error": "nmcli is not installed"}
    args = [
        "nmcli",
        "-t",
        "-f",
        "IN-USE,SSID,SECURITY,SIGNAL,FREQ,CHAN,DEVICE",
        "device",
        "wifi",
        "list",
    ]
    if rescan:
        args += ["--rescan", "yes"]
    run = try_run(args, timeout=12)
    if not run.launched:
        return {"available": False, "networks": [], "error": run.error}
    networks = _parse_wifi_list(run.stdout) if run.ok else []
    return {
        "available": True,
        "networks": networks[:40],
        "error": None if run.ok else (run.error or run.stderr.strip() or "nmcli failed"),
    }


def connect_wifi(ssid: str, password: str | None = None) -> dict[str, Any]:
    # @use: low use — purpose: join Wi-Fi via allowlisted nmcli argv
    if not ssid or len(ssid) > 128:
        return {"ok": False, "error": "invalid SSID"}
    if password is not None and len(password) > 256:
        return {"ok": False, "error": "invalid password"}
    if not available():
        return {"ok": False, "error": "nmcli is not installed"}
    argv = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        argv += ["password", password]
    run = try_run(argv, timeout=35)
    return {
        "ok": run.ok,
        "message": run.stdout.strip(),
        "error": None if run.ok else (run.error or run.stderr.strip() or "connect failed"),
    }


def disconnect(device: str) -> dict[str, Any]:
    # @use: low use — purpose: disconnect nmcli device by validated name
    if not available():
        return {"ok": False, "error": "nmcli is not installed"}
    if not device or len(device) > 32 or not all(c.isalnum() or c in "-_." for c in device):
        return {"ok": False, "error": "invalid device"}
    run = try_run(["nmcli", "device", "disconnect", device], timeout=15)
    return {
        "ok": run.ok,
        "message": run.stdout.strip(),
        "error": None if run.ok else (run.error or run.stderr.strip() or "disconnect failed"),
    }
