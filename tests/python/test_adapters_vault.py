from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.vault import FEATURE_PACKAGES, VaultAdapter, feature_row


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class VaultCatalogTests(unittest.TestCase):
    def test_feature_packages_cover_apps_ids(self):
        for key in ("kitty", "tmux", "rofi", "waybar", "hyprland", "bluetooth", "claude"):
            self.assertIn(key, FEATURE_PACKAGES)

    def test_feature_row_marks_non_apt_not_installable(self):
        row = feature_row("vapor", FEATURE_PACKAGES["vapor"])
        self.assertFalse(row["installable"])
        self.assertEqual(row["apt"], [])


class VaultAdapterTests(unittest.TestCase):
    def test_snapshot_lists_features_and_install_gate(self):
        adapter = VaultAdapter(pkexec="", apt_get="", dpkg_query="", cache_ttl=0)
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertFalse(snap["can_install"])
        self.assertIn("kitty", snap["features"])
        self.assertEqual(snap["feature_order"][0], "kitty")

    @patch("lmdesktopplus.adapters.vault.package_installed", return_value=True)
    @patch("lmdesktopplus.adapters.vault.run_capture")
    def test_install_uses_allowlisted_packages_only(self, run_capture, _installed):
        run_capture.return_value = completed(returncode=0)
        adapter = VaultAdapter(
            pkexec="/usr/bin/pkexec",
            apt_get="/usr/bin/apt-get",
            dpkg_query="",
            cache_ttl=0,
        )
        result = adapter.command("install", {"id": "kitty"})
        self.assertTrue(result.get("ok"))
        argv = run_capture.call_args[0][0]
        self.assertEqual(argv[:4], ["/usr/bin/pkexec", "/usr/bin/apt-get", "install", "-y"])
        self.assertIn("kitty", argv)

    def test_install_rejects_unknown_and_non_apt_features(self):
        adapter = VaultAdapter(pkexec="/pkexec", apt_get="/apt-get", cache_ttl=0)
        unknown = adapter.command("forge_pack", {"id": "not-real"})
        self.assertFalse(unknown.get("ok"))
        no_apt = adapter.command("install", {"id": "vapor"})
        self.assertFalse(no_apt.get("ok"))

    def test_install_unavailable_without_pkexec(self):
        adapter = VaultAdapter(pkexec="", apt_get="/apt-get", cache_ttl=0)
        result = adapter.command("install", {"id": "tmux"})
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error_code"), "unavailable")


if __name__ == "__main__":
    unittest.main()
