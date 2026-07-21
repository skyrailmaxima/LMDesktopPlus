from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lmdesktopplus.adapters.audio import (
    AudioAdapter,
    parse_pactl_mute,
    parse_pactl_volume,
    parse_wpctl_volume,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class AudioParserTests(unittest.TestCase):
    def test_parse_wpctl_volume_and_muted_state(self):
        self.assertEqual(parse_wpctl_volume("Volume: 0.47 [MUTED]\n"), (47, True))
        self.assertEqual(parse_wpctl_volume("Volume: 1.00\n"), (100, False))

    def test_parse_pactl_volume_uses_first_percentage(self):
        output = "Volume: front-left: 32768 / 50% / -18.06 dB, front-right: 32768 / 50% / -18.06 dB"
        self.assertEqual(parse_pactl_volume(output), 50)

    def test_parse_pactl_mute(self):
        self.assertTrue(parse_pactl_mute("Mute: yes\n"))
        self.assertFalse(parse_pactl_mute("Mute: no\n"))


class AudioAdapterTests(unittest.TestCase):
    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/wpctl")
    @patch("lmdesktopplus.adapters.audio.run_capture")
    def test_snapshot_uses_wpctl_and_caches_result(self, run_capture, _first_executable):
        run_capture.return_value = completed("Volume: 0.63 [MUTED]\n")
        adapter = AudioAdapter()

        expected = {"available": True, "backend": "wpctl", "volume": 63, "muted": True}
        self.assertEqual(adapter.snapshot(), expected)
        self.assertEqual(adapter.snapshot(), expected)
        run_capture.assert_called_once_with(
            ["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            timeout=3,
        )

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/pactl")
    @patch("lmdesktopplus.adapters.audio.run_capture")
    def test_snapshot_falls_back_to_pactl(self, run_capture, _first_executable):
        run_capture.side_effect = [
            completed("Volume: front-left: 49152 / 75% / -7.50 dB\n"),
            completed("Mute: no\n"),
        ]
        self.assertEqual(
            AudioAdapter().snapshot(),
            {"available": True, "backend": "pactl", "volume": 75, "muted": False},
        )

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value=None)
    def test_snapshot_fails_soft_when_audio_tools_are_missing(self, _first_executable):
        self.assertEqual(AudioAdapter().snapshot(), {"available": False})

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/wpctl")
    @patch(
        "lmdesktopplus.adapters.audio.run_capture",
        side_effect=subprocess.TimeoutExpired(["wpctl"], 3),
    )
    def test_snapshot_fails_soft_when_audio_query_times_out(self, _run_capture, _first_executable):
        snapshot = AudioAdapter().snapshot()

        self.assertFalse(snapshot["available"])
        self.assertIn("timed out", snapshot["last_error"])

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/wpctl")
    @patch("lmdesktopplus.adapters.audio.run_capture", return_value=completed())
    def test_set_volume_clamps_integer_values(self, run_capture, _first_executable):
        adapter = AudioAdapter()

        self.assertEqual(adapter.command("set_volume", {"volume": 150}), {"ok": True, "volume": 100})
        self.assertEqual(adapter.command("set_volume", {"volume": -9}), {"ok": True, "volume": 0})
        self.assertEqual(
            run_capture.call_args_list[0].args[0],
            ["/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "100%"],
        )
        self.assertEqual(
            run_capture.call_args_list[1].args[0],
            ["/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0%"],
        )

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/pactl")
    @patch("lmdesktopplus.adapters.audio.run_capture", return_value=completed())
    def test_toggle_mute_uses_pactl_default_sink(self, run_capture, _first_executable):
        result = AudioAdapter().command("toggle_mute", {})

        self.assertEqual(result, {"ok": True})
        run_capture.assert_called_once_with(
            ["/usr/bin/pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
            timeout=3,
        )

    @patch("lmdesktopplus.adapters.audio.first_executable", return_value="/usr/bin/wpctl")
    def test_commands_reject_invalid_payloads_and_unknown_names(self, _first_executable):
        adapter = AudioAdapter()

        self.assertFalse(adapter.command("set_volume", {"volume": "loud"})["ok"])
        self.assertFalse(adapter.command("not-a-command", {})["ok"])


if __name__ == "__main__":
    unittest.main()
