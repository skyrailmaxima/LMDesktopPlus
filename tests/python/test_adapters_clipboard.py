from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.clipboard import ClipboardAdapter


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class ClipboardAdapterTests(unittest.TestCase):
    def test_unavailable_without_tools(self):
        self.assertEqual(
            ClipboardAdapter(
                session_type="wayland",
                wl_paste="",
                wl_copy="",
                xclip="",
            ).snapshot(),
            {"available": False},
        )

    @patch("lmdesktopplus.adapters.clipboard.run_capture")
    def test_wayland_peek_truncates_and_caches(self, run_capture):
        run_capture.return_value = completed("hello " + ("x" * 600))
        adapter = ClipboardAdapter(
            session_type="wayland",
            wl_paste="/usr/bin/wl-paste",
            wl_copy="/usr/bin/wl-copy",
            xclip=None,
            cache_ttl=2.0,
        )
        snap = adapter.snapshot()
        self.assertTrue(snap["available"])
        self.assertEqual(snap["backend"], "wl-clipboard")
        self.assertTrue(snap["truncated"])
        self.assertEqual(len(snap["preview"]), 500)
        adapter.snapshot()
        run_capture.assert_called_once_with(
            ["/usr/bin/wl-paste", "-n"],
            timeout=3,
        )

    @patch("lmdesktopplus.adapters.clipboard.run_capture")
    def test_x11_peek_uses_xclip(self, run_capture):
        run_capture.return_value = completed("clip text")
        adapter = ClipboardAdapter(
            session_type="x11",
            wl_paste=None,
            wl_copy=None,
            xclip="/usr/bin/xclip",
        )
        snap = adapter.snapshot()
        self.assertEqual(snap["preview"], "clip text")
        self.assertEqual(snap["backend"], "xclip")
        run_capture.assert_called_once_with(
            ["/usr/bin/xclip", "-selection", "clipboard", "-o"],
            timeout=3,
        )

    @patch("lmdesktopplus.adapters.clipboard.run_capture", return_value=completed())
    def test_copy_rejects_oversized_payload(self, run_capture):
        adapter = ClipboardAdapter(
            session_type="wayland",
            wl_paste="/usr/bin/wl-paste",
            wl_copy="/usr/bin/wl-copy",
            xclip=None,
        )
        huge = "a" * (64 * 1024 + 1)
        self.assertFalse(adapter.command("copy", {"text": huge})["ok"])
        run_capture.assert_not_called()

    @patch("lmdesktopplus.adapters.clipboard.run_capture", return_value=completed())
    def test_copy_wayland_uses_stdin(self, run_capture):
        adapter = ClipboardAdapter(
            session_type="wayland",
            wl_paste="/usr/bin/wl-paste",
            wl_copy="/usr/bin/wl-copy",
            xclip=None,
        )
        result = adapter.command("copy", {"text": "paste me"})
        self.assertEqual(result["ok"], True)
        self.assertEqual(run_capture.call_args.args[0], ["/usr/bin/wl-copy"])
        self.assertEqual(run_capture.call_args.kwargs.get("input_text"), "paste me")

    @patch("lmdesktopplus.adapters.clipboard.run_capture", return_value=completed())
    def test_clear_copies_empty_string(self, run_capture):
        adapter = ClipboardAdapter(
            session_type="x11",
            wl_paste=None,
            wl_copy=None,
            xclip="/usr/bin/xclip",
        )
        self.assertEqual(adapter.command("clear", {})["ok"], True)
        self.assertEqual(
            run_capture.call_args.args[0],
            ["/usr/bin/xclip", "-selection", "clipboard"],
        )
        self.assertEqual(run_capture.call_args.kwargs.get("input_text"), "")

    def test_history_stays_in_memory(self):
        adapter = ClipboardAdapter(
            session_type="wayland",
            wl_paste="/usr/bin/wl-paste",
            wl_copy="/usr/bin/wl-copy",
            xclip=None,
        )
        with patch("lmdesktopplus.adapters.clipboard.run_capture", return_value=completed()):
            for i in range(25):
                adapter.command("copy", {"text": f"item-{i}"})
        history = adapter.command("history", {})
        self.assertTrue(history["ok"])
        self.assertEqual(len(history["items"]), 20)
        self.assertEqual(history["items"][0], "item-24")


if __name__ == "__main__":
    unittest.main()
