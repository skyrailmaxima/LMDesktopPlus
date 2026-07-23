from __future__ import annotations

from typing import Any

from .util import executable, run_capture


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


def current() -> dict[str, Any]:
    if not available():
        return {"available": False, "connections": []}
    cp = run_capture(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show", "--active"])
    rows = []
    if cp.returncode == 0:
        for line in cp.stdout.splitlines():
            parts = _split_nmcli(line)
            if len(parts) == 4:
                rows.append({"name": parts[0], "type": parts[1], "device": parts[2], "state": parts[3]})
    return {"available": True, "connections": rows}


def scan_wifi(rescan: bool = False) -> dict[str, Any]:
    if not available():
        return {"available": False, "networks": [], "error": "nmcli is not installed"}
    args = ["nmcli", "-t", "-f", "IN-USE,SSID,SECURITY,SIGNAL,FREQ,CHAN,DEVICE", "device", "wifi", "list"]
    if rescan:
        args += ["--rescan", "yes"]
    cp = run_capture(args, timeout=12)
    networks = []
    if cp.returncode == 0:
        for line in cp.stdout.splitlines():
            parts = _split_nmcli(line)
            if len(parts) < 7:
                continue
            in_use, ssid, security, signal, freq, chan, device = parts[:7]
            if not ssid:
                continue
            try:
                signal_i = int(signal)
            except ValueError:
                signal_i = 0
            networks.append({
                "active": in_use.strip() == "*",
                "ssid": ssid,
                "security": security or "open",
                "signal": signal_i,
                "frequency": freq,
                "channel": chan,
                "device": device,
            })
    networks.sort(key=lambda row: (not row["active"], -row["signal"], row["ssid"].lower()))
    return {"available": True, "networks": networks[:40], "error": cp.stderr.strip() if cp.returncode else None}


def connect_wifi(ssid: str, password: str | None = None) -> dict[str, Any]:
    if not ssid or len(ssid) > 128:
        return {"ok": False, "error": "invalid SSID"}
    if password is not None and len(password) > 256:
        return {"ok": False, "error": "invalid password"}
    if not available():
        return {"ok": False, "error": "nmcli is not installed"}
    argv = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        argv += ["password", password]
    cp = run_capture(argv, timeout=35)
    return {"ok": cp.returncode == 0, "message": cp.stdout.strip(), "error": cp.stderr.strip() if cp.returncode else None}


def disconnect(device: str) -> dict[str, Any]:
    if not available():
        return {"ok": False, "error": "nmcli is not installed"}
    if not device or len(device) > 32 or not all(c.isalnum() or c in "-_." for c in device):
        return {"ok": False, "error": "invalid device"}
    cp = run_capture(["nmcli", "device", "disconnect", device], timeout=15)
    return {"ok": cp.returncode == 0, "message": cp.stdout.strip(), "error": cp.stderr.strip() if cp.returncode else None}
