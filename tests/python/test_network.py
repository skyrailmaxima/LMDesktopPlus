from __future__ import annotations

import unittest

from lmdesktopplus.network import _split_nmcli, connect_wifi


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


if __name__ == "__main__":
    unittest.main()
