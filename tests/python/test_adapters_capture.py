from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.capture import CaptureAdapter


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class CaptureAdapterTests(unittest.TestCase):
    def test_unavailable_without_backends(self):
        self.assertEqual(
            CaptureAdapter(
                session_type="wayland",
                grim="",
                slurp="",
                gnome_screenshot="",
            ).snapshot()["available"],
            False,
        )

    def test_wayland_capability_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CaptureAdapter(
                session_type="wayland",
                grim="/usr/bin/grim",
                slurp="/usr/bin/slurp",
                gnome_screenshot=None,
                save_dir=Path(tmp),
            )
            snap = adapter.snapshot()
            self.assertTrue(snap["available"])
            self.assertEqual(snap["backend"], "grim")
            self.assertTrue(snap["region_available"])

    @patch("lmdesktopplus.adapters.capture.run_capture", return_value=completed())
    def test_full_grim_writes_under_save_dir(self, run_capture):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            adapter = CaptureAdapter(
                session_type="wayland",
                grim="/usr/bin/grim",
                slurp="/usr/bin/slurp",
                gnome_screenshot=None,
                save_dir=save_dir,
            )
            # Pretend grim created the file
            def fake_run(argv, timeout=4.0):
                Path(argv[-1]).write_bytes(b"png")
                return completed()

            run_capture.side_effect = fake_run
            result = adapter.command("full", {})
            self.assertTrue(result["ok"])
            path = Path(result["path"])
            self.assertTrue(str(path).startswith(str(save_dir)))
            self.assertTrue(path.exists())
            self.assertEqual(run_capture.call_args.args[0][0], "/usr/bin/grim")

    @patch("lmdesktopplus.adapters.capture.run_capture")
    def test_region_rejects_bad_geometry(self, run_capture):
        run_capture.side_effect = [completed("bad-geom\n")]
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CaptureAdapter(
                session_type="wayland",
                grim="/usr/bin/grim",
                slurp="/usr/bin/slurp",
                gnome_screenshot=None,
                save_dir=Path(tmp),
            )
            result = adapter.command("region", {})
            self.assertFalse(result["ok"])
            self.assertIn("geometry", result["error"])

    @patch("lmdesktopplus.adapters.capture.run_capture")
    def test_region_grim_with_valid_slurp(self, run_capture):
        def fake_run(argv, timeout=4.0):
            if argv[0] == "/usr/bin/slurp":
                return completed("10,20 300x200\n")
            Path(argv[-1]).write_bytes(b"png")
            return completed()

        run_capture.side_effect = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CaptureAdapter(
                session_type="wayland",
                grim="/usr/bin/grim",
                slurp="/usr/bin/slurp",
                gnome_screenshot=None,
                save_dir=Path(tmp),
            )
            result = adapter.command("region", {})
            self.assertTrue(result["ok"])
            grim_argv = run_capture.call_args_list[1].args[0]
            self.assertEqual(grim_argv[:3], ["/usr/bin/grim", "-g", "10,20 300x200"])
            self.assertTrue(grim_argv[3].endswith(".png"))

    @patch("lmdesktopplus.adapters.capture.run_capture")
    def test_cinnamon_full_uses_gnome_screenshot(self, run_capture):
        def fake_run(argv, timeout=4.0):
            Path(argv[argv.index("-f") + 1]).write_bytes(b"png")
            return completed()

        run_capture.side_effect = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CaptureAdapter(
                session_type="x11",
                grim=None,
                slurp=None,
                gnome_screenshot="/usr/bin/gnome-screenshot",
                save_dir=Path(tmp),
            )
            result = adapter.command("full", {})
            self.assertTrue(result["ok"])
            argv = run_capture.call_args.args[0]
            self.assertEqual(argv[0], "/usr/bin/gnome-screenshot")
            self.assertIn("-f", argv)

    def test_rejects_user_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CaptureAdapter(
                session_type="wayland",
                grim="/usr/bin/grim",
                slurp=None,
                gnome_screenshot=None,
                save_dir=Path(tmp),
            )
            self.assertFalse(adapter.command("full", {"path": "/tmp/evil.png"})["ok"])


if __name__ == "__main__":
    unittest.main()
