from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.display import DisplayAdapter


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class DisplayAdapterTests(unittest.TestCase):
    @patch("lmdesktopplus.adapters.display.run_capture")
    def test_snapshot_uses_brightnessctl_and_caches_result(self, run_capture):
        run_capture.side_effect = [completed("240\n"), completed("400\n")]
        adapter = DisplayAdapter(
            cache_ttl=10,
            brightnessctl="/usr/bin/brightnessctl",
            sysfs_root=Path("/missing"),
        )

        expected = {
            "available": True,
            "backend": "brightnessctl",
            "brightness": 60,
            "writable": True,
        }
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(run_capture.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in run_capture.call_args_list],
            [
                ["/usr/bin/brightnessctl", "g"],
                ["/usr/bin/brightnessctl", "m"],
            ],
        )

    @patch("lmdesktopplus.adapters.display.run_capture", return_value=completed())
    def test_set_brightness_clamps_to_one_through_one_hundred(self, run_capture):
        adapter = DisplayAdapter(
            brightnessctl="/usr/bin/brightnessctl",
            sysfs_root=Path("/missing"),
        )

        self.assertEqual(
            adapter.command("set_brightness", {"brightness": 0}),
            {"ok": True, "brightness": 1},
        )
        self.assertEqual(
            adapter.command("set_brightness", {"brightness": 120}),
            {"ok": True, "brightness": 100},
        )
        self.assertEqual(
            [call.args[0] for call in run_capture.call_args_list],
            [
                ["/usr/bin/brightnessctl", "s", "1%"],
                ["/usr/bin/brightnessctl", "s", "100%"],
            ],
        )

    def test_snapshot_reads_sysfs_as_read_only_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            device = Path(temp) / "intel_backlight"
            device.mkdir()
            (device / "brightness").write_text("75\n", encoding="utf-8")
            (device / "max_brightness").write_text("300\n", encoding="utf-8")

            snapshot = DisplayAdapter(
                brightnessctl=None,
                sysfs_root=Path(temp),
            ).snapshot()

        self.assertEqual(
            snapshot,
            {
                "available": True,
                "backend": "sysfs",
                "brightness": 25,
                "writable": False,
            },
        )

    @patch(
        "lmdesktopplus.adapters.display.run_capture",
        side_effect=subprocess.TimeoutExpired(["brightnessctl"], 3),
    )
    def test_snapshot_fails_soft_when_brightnessctl_times_out(self, _run_capture):
        snapshot = DisplayAdapter(
            brightnessctl="/usr/bin/brightnessctl",
            sysfs_root=Path("/missing"),
        ).snapshot()

        self.assertFalse(snapshot["available"])
        self.assertIn("timed out", snapshot["last_error"])

    def test_missing_controls_and_invalid_commands_fail_soft(self):
        adapter = DisplayAdapter(brightnessctl=None, sysfs_root=Path("/missing"))

        self.assertEqual(adapter.snapshot(), {"available": False})
        self.assertFalse(adapter.command("set_brightness", {"brightness": "bright"})["ok"])
        self.assertFalse(adapter.command("unknown", {})["ok"])

    def test_sysfs_fallback_rejects_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            device = Path(temp) / "panel"
            device.mkdir()
            (device / "brightness").write_text("50\n", encoding="utf-8")
            (device / "max_brightness").write_text("100\n", encoding="utf-8")
            adapter = DisplayAdapter(brightnessctl=None, sysfs_root=Path(temp))

            result = adapter.command("set_brightness", {"brightness": 50})

        self.assertFalse(result["ok"])
        self.assertIn("read-only", result["error"])


if __name__ == "__main__":
    unittest.main()
