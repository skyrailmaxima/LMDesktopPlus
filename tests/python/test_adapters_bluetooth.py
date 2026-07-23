from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.bluetooth import (
    BluetoothAdapter,
    parse_devices,
    parse_powered,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


SHOW_POWERED = """Controller AA:BB:CC:DD:EE:FF (public)
        Name: Host
        Powered: yes
        Discovering: no
"""

SHOW_OFF = """Controller AA:BB:CC:DD:EE:FF (public)
        Powered: no
"""

DEVICES = """Device 11:22:33:44:55:66 Headphones
Device AA:BB:CC:11:22:33 Keyboard
"""

CONNECTED = """Device 11:22:33:44:55:66 Headphones
"""


class BluetoothParserTests(unittest.TestCase):
    def test_parse_powered(self):
        self.assertTrue(parse_powered(SHOW_POWERED))
        self.assertFalse(parse_powered(SHOW_OFF))
        self.assertFalse(parse_powered("no Powered line"))

    def test_parse_devices_marks_connected(self):
        devices = parse_devices(DEVICES, CONNECTED)
        self.assertEqual(
            devices,
            [
                {"mac": "11:22:33:44:55:66", "name": "Headphones", "connected": True},
                {"mac": "AA:BB:CC:11:22:33", "name": "Keyboard", "connected": False},
            ],
        )


class BluetoothAdapterTests(unittest.TestCase):
    def test_snapshot_fails_soft_when_bluetoothctl_missing(self):
        self.assertEqual(
            BluetoothAdapter(bluetoothctl=None).snapshot(),
            {"available": False},
        )

    @patch("lmdesktopplus.adapters.bluetooth.run_capture")
    def test_snapshot_lists_devices_and_caches(self, run_capture):
        run_capture.side_effect = [
            completed(SHOW_POWERED),
            completed(DEVICES),
            completed(CONNECTED),
        ]
        adapter = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl", cache_ttl=5.0)

        expected = {
            "available": True,
            "powered": True,
            "scanning": False,
            "devices": [
                {"mac": "11:22:33:44:55:66", "name": "Headphones", "connected": True},
                {"mac": "AA:BB:CC:11:22:33", "name": "Keyboard", "connected": False},
            ],
        }
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(run_capture.call_count, 3)

    @patch("lmdesktopplus.adapters.bluetooth.run_capture")
    def test_snapshot_fails_soft_on_timeout(self, run_capture):
        run_capture.side_effect = subprocess.TimeoutExpired(["bluetoothctl"], 3)
        snapshot = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl").snapshot()
        self.assertFalse(snapshot["available"])
        self.assertIn("timed out", snapshot["last_error"])

    @patch("lmdesktopplus.adapters.bluetooth.run_capture", return_value=completed())
    def test_power_on_and_off(self, run_capture):
        adapter = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl")
        self.assertEqual(adapter.command("power", {"on": True}), {"ok": True, "powered": True})
        self.assertEqual(adapter.command("power", {"on": False}), {"ok": True, "powered": False})
        self.assertEqual(
            run_capture.call_args_list[0].args[0],
            ["/usr/bin/bluetoothctl", "power", "on"],
        )
        self.assertEqual(
            run_capture.call_args_list[1].args[0],
            ["/usr/bin/bluetoothctl", "power", "off"],
        )

    @patch("lmdesktopplus.adapters.bluetooth.run_capture")
    def test_power_blocked_returns_rfkill_hint(self, run_capture):
        run_capture.return_value = completed(
            stderr="Failed to set power on: org.bluez.Error.Blocked",
            returncode=1,
        )
        result = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl").command(
            "power", {"on": True}
        )
        self.assertFalse(result["ok"])
        self.assertIn("rfkill unblock bluetooth", result["error"])

    @patch("lmdesktopplus.adapters.bluetooth.run_capture")
    def test_scan_uses_timeout_then_refreshes_devices(self, run_capture):
        run_capture.side_effect = [
            completed(),  # scan
            completed(SHOW_POWERED),
            completed(DEVICES),
            completed(CONNECTED),
        ]
        adapter = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl")
        result = adapter.command("scan", {})
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["devices"]), 2)
        self.assertEqual(
            run_capture.call_args_list[0].args[0],
            ["/usr/bin/bluetoothctl", "--timeout", "5", "scan", "on"],
        )

    @patch("lmdesktopplus.adapters.bluetooth.run_capture", return_value=completed())
    def test_connect_and_disconnect_validate_mac(self, run_capture):
        adapter = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl")
        self.assertFalse(adapter.command("connect", {"mac": "bad"})["ok"])
        self.assertEqual(
            adapter.command("connect", {"mac": "11:22:33:44:55:66"}),
            {"ok": True, "mac": "11:22:33:44:55:66"},
        )
        self.assertEqual(
            adapter.command("disconnect", {"mac": "aa:bb:cc:dd:ee:ff"}),
            {"ok": True, "mac": "AA:BB:CC:DD:EE:FF"},
        )
        self.assertEqual(
            run_capture.call_args_list[0].args[0],
            ["/usr/bin/bluetoothctl", "connect", "11:22:33:44:55:66"],
        )
        self.assertEqual(
            run_capture.call_args_list[1].args[0],
            ["/usr/bin/bluetoothctl", "disconnect", "AA:BB:CC:DD:EE:FF"],
        )

    def test_unknown_command_rejected(self):
        adapter = BluetoothAdapter(bluetoothctl="/usr/bin/bluetoothctl")
        self.assertFalse(adapter.command("pair", {})["ok"])


if __name__ == "__main__":
    unittest.main()
