from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.network import _split_nmcli, connect_wifi, current


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class NetworkParsingTests(unittest.TestCase):
    def test_split_nmcli_preserves_escaped_colons(self) -> None:
        self.assertEqual(
            _split_nmcli(r"*:Lab\:IoT:WPA2:87:5220:44:wlp2s0"),
            ["*", "Lab:IoT", "WPA2", "87", "5220", "44", "wlp2s0"],
        )

    def test_split_nmcli_preserves_backslashes(self) -> None:
        self.assertEqual(
            _split_nmcli(r"Office\\West:802-11-wireless:wlp2s0:activated"),
            [r"Office\West", "802-11-wireless", "wlp2s0", "activated"],
        )

    def test_connect_wifi_rejects_oversized_password(self) -> None:
        result = connect_wifi("home", "x" * 257)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid password")


class NetworkCurrentTests(unittest.TestCase):
    @patch("lmdesktopplus.network.available", return_value=True)
    @patch("lmdesktopplus.preopt.run_capture")
    def test_current_parses_active_rows(self, run_capture, _avail):
        run_capture.return_value = completed("Home:vpn:tun0:activated\n")
        snap = current()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["connections"][0]["name"], "Home")

    @patch("lmdesktopplus.network.available", return_value=True)
    @patch(
        "lmdesktopplus.preopt.run_capture",
        side_effect=subprocess.TimeoutExpired(["nmcli"], 4),
    )
    def test_current_timeout_fails_soft(self, _run, _avail):
        snap = current()
        self.assertFalse(snap["available"])
        self.assertIn("timed out", snap.get("last_error", ""))


if __name__ == "__main__":
    unittest.main()
