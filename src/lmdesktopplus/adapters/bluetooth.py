"""Bluetooth power/scan/connect via bluetoothctl (Stage B).

@use levels: snapshot is medium; power/scan/connect are low use.
Preoptimized: try_run host edge; Outcome snapshot probe; one loop per parser.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import Outcome, try_run
from ..util import executable
from .base import dispatch_command

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")
_DEVICE_RE = re.compile(
    r"^Device\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\s+(.*)$"
)
_POWERED_RE = re.compile(r"^\s*Powered:\s*(yes|no)\s*$", re.IGNORECASE | re.MULTILINE)


@register_fn(
    "bluetooth.parse_powered",
    UseLevel.MEDIUM,
    "Parse bluetoothctl show Powered: yes/no",
)
def parse_powered(output: str) -> bool:
    # @use: medium use — purpose: Desktop Bluetooth power chip
    match = _POWERED_RE.search(output)
    return bool(match and match.group(1).lower() == "yes")


def _connected_macs(connected_output: str) -> set[str]:
    # @use: medium use — purpose: one-loop Connected device MAC set
    connected: set[str] = set()
    for line in connected_output.splitlines():
        match = _DEVICE_RE.match(line.strip())
        match is not None and connected.add(match.group(1).upper())
    return connected


@register_fn(
    "bluetooth.parse_devices",
    UseLevel.MEDIUM,
    "Parse bluetoothctl devices (+ Connected) into UI rows",
)
def parse_devices(known_output: str, connected_output: str = "") -> list[dict[str, Any]]:
    # @use: medium use — purpose: Bluetooth device list (one loop over known)
    connected = _connected_macs(connected_output)
    devices: list[dict[str, Any]] = []
    for line in known_output.splitlines():
        match = _DEVICE_RE.match(line.strip())
        if match is None:
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
    # @use: medium use — purpose: validate Bluetooth MAC from UI payload
    if not isinstance(value, str):
        return None
    mac = value.strip().upper()
    return mac if _MAC_RE.match(mac) else None


class BluetoothAdapter:
    """Fail-soft BlueZ control through bluetoothctl."""

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
        # @use: medium use — purpose: Bluetooth panel poll via bluetoothctl
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        probed = self._probe_adapter()
        snapshot = (
            probed.value
            if probed.ok
            else {"available": False, "last_error": probed.error}
        )
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_adapter(self) -> Outcome:
        # @use: medium use — purpose: show+devices+Connected without raises
        show = try_run([self.bluetoothctl, "show"], timeout=3)
        if not show.ok:
            return Outcome.fail(show.error or show.stderr.strip() or "bluetoothctl show failed")
        known = try_run([self.bluetoothctl, "devices"], timeout=3)
        if not known.ok:
            return Outcome.fail(
                known.error or known.stderr.strip() or "bluetoothctl devices failed"
            )
        connected = try_run([self.bluetoothctl, "devices", "Connected"], timeout=3)
        connected_out = connected.stdout if connected.ok else ""
        return Outcome.success(
            {
                "available": True,
                "powered": parse_powered(show.stdout),
                "scanning": False,
                "devices": parse_devices(known.stdout, connected_out),
            }
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: power/scan/connect via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "power": self._cmd_power,
            "scan": self._cmd_scan,
            "connect": lambda payload: self._cmd_device("connect", payload),
            "disconnect": lambda payload: self._cmd_device("disconnect", payload),
        }

    def _require_bluetoothctl(self, action):
        return (
            {"ok": False, "error": "bluetoothctl is not installed"}
            if not self.available()
            else action()
        )

    def _cmd_power(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._require_bluetoothctl(lambda: self._power_payload(payload))

    def _power_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        on = payload.get("on")
        return (
            {"ok": False, "error": "on must be a boolean"}
            if not isinstance(on, bool)
            else self._power(on)
        )

    def _cmd_scan(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return self._require_bluetoothctl(self._scan)

    def _cmd_device(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            mac = normalize_mac(payload.get("mac"))
            return (
                {"ok": False, "error": "mac must be a Bluetooth address"}
                if mac is None
                else self._connect_or_disconnect(action, mac)
            )

        return self._require_bluetoothctl(run)

    def _power(self, on: bool) -> dict[str, Any]:
        # @use: low use — purpose: bluetoothctl power on/off via try_run
        state = "on" if on else "off"
        run = try_run([self.bluetoothctl, "power", state], timeout=5)
        if not run.launched:
            return {"ok": False, "error": run.error}
        if not run.ok:
            error = run.stderr.strip() or f"bluetoothctl power {state} failed"
            blocked = "Blocked" in error or "org.bluez.Error.Blocked" in error
            return {
                "ok": False,
                "error": f"{error}. Try: rfkill unblock bluetooth" if blocked else error,
            }
        self._cached_snapshot = None
        return {"ok": True, "powered": on}

    def _scan(self) -> dict[str, Any]:
        # @use: low use — purpose: timed bluetoothctl scan then refresh devices
        run = try_run(
            [self.bluetoothctl, "--timeout", "5", "scan", "on"],
            timeout=12,
        )
        if not run.launched:
            return {"ok": False, "error": run.error}
        if not run.ok:
            return {
                "ok": False,
                "error": run.stderr.strip() or "bluetoothctl scan failed",
            }
        self._cached_snapshot = None
        snap = self.snapshot()
        return {
            "ok": True,
            "devices": snap.get("devices", []),
            "powered": snap.get("powered", False),
        }

    def _connect_or_disconnect(self, name: str, mac: str) -> dict[str, Any]:
        # @use: low use — purpose: bluetoothctl connect/disconnect one MAC
        run = try_run([self.bluetoothctl, name, mac], timeout=15)
        if not run.launched:
            return {"ok": False, "error": run.error}
        if not run.ok:
            return {
                "ok": False,
                "error": run.stderr.strip() or f"bluetoothctl {name} failed",
            }
        self._cached_snapshot = None
        return {"ok": True, "mac": mac}
