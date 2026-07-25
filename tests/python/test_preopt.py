from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.preopt import (
    Outcome,
    clamp_int,
    first_ok_scan,
    parse_float,
    parse_int,
    try_run,
)


class PreoptParseTests(unittest.TestCase):
    def test_parse_int_rejects_bool_and_junk(self):
        self.assertEqual(parse_int(42), 42)
        self.assertEqual(parse_int("7"), 7)
        self.assertIsNone(parse_int(True))
        self.assertIsNone(parse_int("loud"))
        self.assertIsNone(parse_int(""))

    def test_parse_float_and_clamp(self):
        self.assertEqual(parse_float("0.63"), 0.63)
        self.assertIsNone(parse_float("nope"))
        self.assertEqual(clamp_int(150, 0, 100), 100)
        self.assertEqual(clamp_int(-3, 0, 100), 0)


class PreoptScanTests(unittest.TestCase):
    def test_first_ok_scan_one_loop_priority(self):
        calls: list[str] = []

        def probe(name: str) -> Outcome:
            calls.append(name)
            return Outcome.fail(f"{name} down") if name == "a" else Outcome.success(name)

        result = first_ok_scan(("a", "b", "c"), probe)
        self.assertTrue(result.ok)
        self.assertEqual(result.value, "b")
        self.assertEqual(calls, ["a", "b"])


class PreoptTryRunTests(unittest.TestCase):
    @patch("lmdesktopplus.preopt.run_capture", return_value=subprocess.CompletedProcess([], 0, "ok", ""))
    def test_try_run_ok(self, _run):
        run = try_run(["true"], timeout=1)
        self.assertTrue(run.ok)
        self.assertEqual(run.stdout, "ok")

    @patch(
        "lmdesktopplus.preopt.run_capture",
        side_effect=subprocess.TimeoutExpired(["slow"], 2),
    )
    def test_try_run_timeout_is_outcome(self, _run):
        run = try_run(["slow"], timeout=2)
        self.assertFalse(run.launched)
        self.assertIn("timed out", run.error)


if __name__ == "__main__":
    unittest.main()
