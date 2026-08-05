from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.updates import UpdatesAdapter, count_upgradable


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


APT_OUT = """Listing...
WARNING: apt does not have a stable CLI interface. Use with caution in scripts.

firefox/noble-updates 1.0 upgradable from 0.9
vim/noble 2.0 [upgradable from: 1.9]
"""


class UpdatesParserTests(unittest.TestCase):
    def test_count_upgradable_ignores_noise(self):
        self.assertEqual(count_upgradable(APT_OUT), 2)
        self.assertEqual(count_upgradable(""), 0)


class UpdatesAdapterTests(unittest.TestCase):
    def test_snapshot_fails_soft_without_apt(self):
        self.assertEqual(
            UpdatesAdapter(apt="", mintupdate="").snapshot(),
            {"available": False},
        )

    @patch("lmdesktopplus.preopt.run_capture")
    def test_snapshot_counts_and_caches(self, run_capture):
        run_capture.return_value = completed(APT_OUT)
        adapter = UpdatesAdapter(
            apt="/usr/bin/apt",
            mintupdate="/usr/bin/mintupdate",
            cache_ttl=600,
        )
        expected = {
            "available": True,
            "count": 2,
            "mintupdate_available": True,
        }
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(adapter.snapshot(), expected)
        run_capture.assert_called_once()

    @patch("lmdesktopplus.preopt.run_capture")
    def test_refresh_invalidates_cache(self, run_capture):
        run_capture.side_effect = [
            completed(APT_OUT),
            completed("Listing...\nfoo/bar 1 upgradable from 0\n"),
        ]
        adapter = UpdatesAdapter(apt="/usr/bin/apt", mintupdate=None, cache_ttl=600)
        self.assertEqual(adapter.snapshot()["count"], 2)
        result = adapter.command("refresh", {})
        self.assertEqual(result, {"ok": True, "count": 1, "mintupdate_available": False})

    @patch("lmdesktopplus.adapters.updates.spawn", return_value=4242)
    def test_open_launches_mintupdate(self, spawn):
        adapter = UpdatesAdapter(apt="/usr/bin/apt", mintupdate="/usr/bin/mintupdate")
        self.assertEqual(adapter.command("open", {}), {"ok": True, "pid": 4242})
        spawn.assert_called_once_with(["/usr/bin/mintupdate"])

    def test_open_fails_without_mintupdate(self):
        adapter = UpdatesAdapter(apt="/usr/bin/apt", mintupdate="")
        self.assertFalse(adapter.command("open", {})["ok"])

    def test_unknown_command(self):
        adapter = UpdatesAdapter(apt="/usr/bin/apt", mintupdate="")
        self.assertFalse(adapter.command("upgrade", {})["ok"])


if __name__ == "__main__":
    unittest.main()
