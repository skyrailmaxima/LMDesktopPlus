from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.media import control, status


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class MediaStatusTests(unittest.TestCase):
    @patch("lmdesktopplus.media.executable", return_value=None)
    def test_unavailable_without_playerctl(self, _exe):
        snap = status()
        self.assertFalse(snap["available"])
        self.assertEqual(snap["status"], "Stopped")

    @patch("lmdesktopplus.media.executable", return_value="/usr/bin/playerctl")
    @patch("lmdesktopplus.preopt.run_capture")
    def test_status_parses_metadata(self, run_capture, _exe):
        run_capture.return_value = completed("Playing\tArtist\tTitle\tAlbum\n")
        snap = status()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["status"], "Playing")
        self.assertEqual(snap["artist"], "Artist")
        self.assertEqual(snap["title"], "Title")

    @patch("lmdesktopplus.media.executable", return_value="/usr/bin/playerctl")
    @patch(
        "lmdesktopplus.preopt.run_capture",
        side_effect=subprocess.TimeoutExpired(["playerctl"], 2),
    )
    def test_status_timeout_is_stopped(self, _run, _exe):
        snap = status()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["status"], "Stopped")


class MediaControlTests(unittest.TestCase):
    def test_rejects_unknown_action(self):
        self.assertFalse(control("shuffle")["ok"])

    @patch("lmdesktopplus.media.executable", return_value="/usr/bin/playerctl")
    @patch("lmdesktopplus.preopt.run_capture", return_value=completed())
    def test_play_pause_ok(self, run_capture, _exe):
        result = control("play-pause")
        self.assertTrue(result["ok"])
        # First host call is the action; status() re-probes metadata afterward.
        self.assertEqual(run_capture.call_args_list[0].args[0], ["playerctl", "play-pause"])


if __name__ == "__main__":
    unittest.main()
