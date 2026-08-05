from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.vpn import (
    VpnAdapter,
    normalize_connection_name,
    parse_vpn_connections,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


ALL_CONNECTIONS = """HomeVPN:vpn::
OfficeWG:wireguard::
WiFi:802-11-wireless:wlan0:activated
Escaped\\:Name:vpn::
"""

ACTIVE_VPN = """HomeVPN:vpn:tun0:activated
WiFi:802-11-wireless:wlan0:activated
"""


class VpnParserTests(unittest.TestCase):
    def test_parse_filters_vpn_types_and_marks_active(self):
        rows = parse_vpn_connections(ALL_CONNECTIONS, {"HomeVPN"})
        self.assertEqual(
            rows,
            [
                {
                    "name": "HomeVPN",
                    "type": "vpn",
                    "device": None,
                    "state": "",
                    "active": True,
                },
                {
                    "name": "Escaped:Name",
                    "type": "vpn",
                    "device": None,
                    "state": "",
                    "active": False,
                },
                {
                    "name": "OfficeWG",
                    "type": "wireguard",
                    "device": None,
                    "state": "",
                    "active": False,
                },
            ],
        )

    def test_normalize_connection_name(self):
        self.assertEqual(normalize_connection_name(" Home VPN "), "Home VPN")
        self.assertIsNone(normalize_connection_name("../evil"))
        self.assertIsNone(normalize_connection_name(""))
        self.assertIsNone(normalize_connection_name(None))


class VpnAdapterTests(unittest.TestCase):
    def test_unavailable_without_nmcli(self):
        self.assertEqual(VpnAdapter(nmcli="").snapshot(), {"available": False})

    @patch("lmdesktopplus.preopt.run_capture")
    def test_snapshot_lists_and_caches(self, run_capture):
        run_capture.side_effect = [completed(ACTIVE_VPN), completed(ALL_CONNECTIONS)]
        adapter = VpnAdapter(nmcli="/usr/bin/nmcli", cache_ttl=5.0)
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["backend"], "nmcli")
        self.assertEqual(snap["active_count"], 1)
        self.assertEqual(snap["connections"][0]["name"], "HomeVPN")
        self.assertTrue(snap["connections"][0]["active"])
        self.assertEqual(adapter.snapshot()["active_count"], 1)
        self.assertEqual(run_capture.call_count, 2)

    @patch("lmdesktopplus.preopt.run_capture", return_value=completed())
    def test_up_and_down(self, run_capture):
        adapter = VpnAdapter(nmcli="/usr/bin/nmcli")
        self.assertEqual(
            adapter.command("up", {"name": "HomeVPN"}),
            {"ok": True, "action": "up", "name": "HomeVPN"},
        )
        self.assertEqual(
            adapter.command("down", {"connection": "OfficeWG"}),
            {"ok": True, "action": "down", "name": "OfficeWG"},
        )
        self.assertEqual(
            run_capture.call_args_list[0].args[0],
            ["/usr/bin/nmcli", "connection", "up", "HomeVPN"],
        )
        self.assertEqual(
            run_capture.call_args_list[1].args[0],
            ["/usr/bin/nmcli", "connection", "down", "OfficeWG"],
        )

    def test_rejects_bad_name_and_unknown_command(self):
        adapter = VpnAdapter(nmcli="/usr/bin/nmcli")
        bad = adapter.command("up", {"name": "bad;rm -rf"})
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error_code"], "invalid_argument")
        unknown = adapter.command("connect", {})
        self.assertEqual(unknown["error_code"], "unavailable")

    @patch("lmdesktopplus.preopt.run_capture")
    def test_permission_errors_are_classified(self, run_capture):
        run_capture.return_value = completed(
            stderr="Error: Connection activation failed: Not authorized",
            returncode=1,
        )
        result = VpnAdapter(nmcli="/usr/bin/nmcli").command("up", {"name": "HomeVPN"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "permission_denied")


if __name__ == "__main__":
    unittest.main()
