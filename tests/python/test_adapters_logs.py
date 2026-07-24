from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.logs import LogsAdapter, sanitize_journal


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class LogsSanitizeTests(unittest.TestCase):
    def test_sanitize_strips_controls_and_caps_lines(self):
        raw = "ok line\n" + ("x" * 10) + "\x00bad\n" + "\n".join(f"line-{i}" for i in range(250))
        lines = sanitize_journal(raw, max_lines=200, max_chars=80_000)
        self.assertLessEqual(len(lines), 200)
        self.assertTrue(all("\x00" not in line for line in lines))
        self.assertTrue(any(line.startswith("line-") for line in lines))


class LogsAdapterTests(unittest.TestCase):
    def test_unavailable_without_journalctl(self):
        self.assertFalse(LogsAdapter(journalctl="").snapshot().get("available"))

    @patch("lmdesktopplus.adapters.logs.run_capture")
    def test_snapshot_returns_sanitized_lines(self, run_capture):
        run_capture.return_value = completed(stdout="2026-07-24T00:00:00 hello\nworld\n")
        adapter = LogsAdapter(journalctl="/usr/bin/journalctl", cache_ttl=0)
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["lines"], ["2026-07-24T00:00:00 hello", "world"])
        refreshed = adapter.command("refresh", {})
        self.assertTrue(refreshed.get("ok"))
        self.assertEqual(refreshed["count"], 2)


if __name__ == "__main__":
    unittest.main()
