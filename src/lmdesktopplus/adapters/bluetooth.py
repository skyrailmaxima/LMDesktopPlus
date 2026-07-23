from __future__ import annotations

import re
import subprocess
import time
from typing import Any

from ..util import executable, run_capture

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")
_DEVICE_RE = re.compile(
    r"^Device\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(.*)$"
)
_POWERED_RE = re.compile(r"^\s*Powered:\s*(yes|no)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_powered(output: str) -> bool:
    match = _POWERED_RE.search(output)
    return bool(match and match.group(1).lower() == "yes")


def parse_devices(known_output: str, connected_output: str = "") -> list[dict[str, Any]]:
    connected: set[str] = set()
    for line in connected_output.splitlines():
        match = _DEVICE_RE.match(line.strip())
        if match:
            connected.add(match.group(1).upper())
    devices: list[dict[str, Any]] = []
    for line in known_output.splitlines():
        match = _DEVICE_RE.match(line.strip())
        if not match:
            continue
        mac = match.group(1).upper()
        name = match.group(2).strip() or mac
        devices.append({
            "mac": mac,
            "name": name,
            "connected": mac in connected,
        })
    return devices


def normalize_mac(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    mac = value.strip().upper()
    if not _MAC_RE.match(mac):
        return None
    return mac


class BluetoothAdapter:
    id = "bluetooth"

    def __init__(
        self,
        cache_ttl: float = 5.0,
        bluetoothctl: str | None = None,
    ) -> None:
        if bluetoothctl is None:
            bluetoothctl = executable("bluetoothctl")
        self.bluetoothctl = bluetoothctl
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.bluetoothctl)

    def snapshot(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            show = run_capture([self.bluetoothctl, "show"], timeout=3)
            if show.returncode != 0:
                raise RuntimeError(show.stderr.strip() or "bluetoothctl show failed")
            known = run_capture([self.bluetoothctl, "devices"], timeout=3)
            if known.returncode != 0:
                raise RuntimeError(known.stderr.strip() or "bluetoothctl devices failed")
            connected = run_capture(
                [self.bluetoothctl, "devices", "Connected"],
                timeout=3,
            )
            connected_out = connected.stdout if connected.returncode == 0 else ""
            snapshot = {
                "available": True,
                "powered": parse_powered(show.stdout),
                "scanning": False,
                "devices": parse_devices(known.stdout, connected_out),
            }
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            snapshot = {
                "available": False,
                "last_error": str(exc),
            }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in {"power", "scan", "connect", "disconnect"}:
            return {"ok": False, "error": f"unknown bluetooth command: {name}"}
        if not self.available():
            return {"ok": False, "error": "bluetoothctl is not installed"}

        if name == "power":
            on = payload.get("on")
            if not isinstance(on, bool):
                return {"ok": False, "error": "on must be a boolean"}
            return self._power(on)
        if name == "scan":
            return self._scan()
        mac = normalize_mac(payload.get("mac"))
        if mac is None:
            return {"ok": False, "error": "mac must be a Bluetooth address"}
        return self._connect_or_disconnect(name, mac)

    def _power(self, on: bool) -> dict[str, Any]:
        state = "on" if on else "off"
        try:
            result = run_capture([self.bluetoothctl, "power", state], timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            error = result.stderr.strip() or f"bluetoothctl power {state} failed"
            if "Blocked" in error or "org.bluez.Error.Blocked" in error:
                error = f"{error}. Try: rfkill unblock bluetooth"
            return {"ok": False, "error": error}
        self._cached_snapshot = None
        return {"ok": True, "powered": on}

    def _scan(self) -> dict[str, Any]:
        try:
            result = run_capture(
                [self.bluetoothctl, "--timeout", "5", "scan", "on"],
                timeout=12,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or "bluetoothctl scan failed",
            }
        self._cached_snapshot = None
        snap = self.snapshot()
        return {
            "ok": True,
            "devices": snap.get("devices", []),
            "powered": snap.get("powered", False),
        }

    def _connect_or_disconnect(self, name: str, mac: str) -> dict[str, Any]:
        try:
            result = run_capture([self.bluetoothctl, name, mac], timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or f"bluetoothctl {name} failed",
            }
        self._cached_snapshot = None
        return {"ok": True, "mac": mac}
