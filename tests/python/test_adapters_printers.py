from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.printers import PrintersAdapter, parse_lpstat


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


LPSTAT = """
printer HP_LaserJet is idle.  enabled since Fri 24 Jul 2026
printer Office_Ink is disabled since Thu 01 Jan 1970
system default destination: HP_LaserJet
"""


class PrintersParseTests(unittest.TestCase):
    def test_parse_lpstat_rows_and_default(self):
        parsed = parse_lpstat(LPSTAT)
        self.assertEqual(parsed["default"], "HP_LaserJet")
        self.assertEqual(parsed["count"], 2)
        names = {row["name"] for row in parsed["printers"]}
        self.assertEqual(names, {"HP_LaserJet", "Office_Ink"})


class PrintersAdapterTests(unittest.TestCase):
    def test_unavailable_without_lpstat(self):
        self.assertEqual(
            PrintersAdapter(lpstat="", printer_ui="").snapshot()["available"],
            False,
        )

    @patch("lmdesktopplus.preopt.run_capture")
    def test_snapshot_and_refresh(self, run_capture):
        run_capture.return_value = completed(stdout=LPSTAT)
        adapter = PrintersAdapter(lpstat="/usr/bin/lpstat", printer_ui="", cache_ttl=0)
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["count"], 2)
        refreshed = adapter.command("refresh", {})
        self.assertTrue(refreshed.get("ok"))

    @patch("lmdesktopplus.adapters.printers.spawn", return_value=4242)
    def test_open_spawns_ui(self, spawn):
        adapter = PrintersAdapter(lpstat="/usr/bin/lpstat", printer_ui="/usr/bin/system-config-printer")
        result = adapter.command("open", {})
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("pid"), 4242)
        spawn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
