from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.actions import (
    ACTION_HANDLERS,
    LAUNCH_HANDLERS,
    ActionRunner,
    wrap_in_terminal,
)


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class WrapInTerminalTests(unittest.TestCase):
    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/kitty")
    def test_kitty_hold_spreads_argv(self, _first):
        self.assertEqual(
            wrap_in_terminal(["tmux", "attach"], hold=True),
            ["/usr/bin/kitty", "--hold", "tmux", "attach"],
        )

    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/kitty")
    def test_kitty_directory_and_hold(self, _first):
        self.assertEqual(
            wrap_in_terminal(["claude"], hold=True, directory="/tmp/work"),
            ["/usr/bin/kitty", "--directory", "/tmp/work", "--hold", "claude"],
        )

    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/gnome-terminal")
    def test_gnome_uses_double_dash(self, _first):
        self.assertEqual(
            wrap_in_terminal(["btop"], hold=True),
            ["/usr/bin/gnome-terminal", "--", "btop"],
        )

    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/xfce4-terminal")
    def test_xfce_joins_command(self, _first):
        self.assertEqual(
            wrap_in_terminal(["tmux", "new"], hold=True),
            ["/usr/bin/xfce4-terminal", "--hold", "--command", "tmux new"],
        )

    @patch("lmdesktopplus.actions.first_executable", return_value=None)
    def test_missing_terminal(self, _first):
        self.assertIsNone(wrap_in_terminal(["btop"]))

    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/local/bin/xterm")
    def test_xterm_spreads_argv(self, _first):
        self.assertEqual(
            wrap_in_terminal(["tmux", "new-session", "-A", "-s", "lmdesktopplus"]),
            ["/usr/local/bin/xterm", "-e", "tmux", "new-session", "-A", "-s", "lmdesktopplus"],
        )


class ActionDispatchTests(unittest.TestCase):
    def test_action_handlers_cover_known_peers(self):
        expected = {
            "launch",
            "lock",
            "logout",
            "suspend",
            "reboot",
            "poweroff",
            "open-config",
        }
        self.assertEqual(set(ACTION_HANDLERS), expected)

    def test_launch_handlers_cover_known_peers(self):
        expected = {
            "terminal",
            "tmux",
            "editor",
            "browser",
            "rofi",
            "docs",
            "monitor",
            "settings",
            "files",
        }
        self.assertEqual(set(LAUNCH_HANDLERS), expected)

    def test_run_unknown_action(self):
        runner = ActionRunner(lambda: {"behavior": {}})
        self.assertEqual(
            runner.run("explode"),
            {"ok": False, "error": "unsupported action"},
        )

    def test_launch_unknown_target(self):
        runner = ActionRunner(lambda: {})
        self.assertEqual(
            runner.launch("spaceship"),
            {"ok": False, "error": "unknown launch target: spaceship"},
        )

    @patch("lmdesktopplus.actions.spawn", return_value=42)
    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/nemo")
    def test_open_config_via_action_map(self, _first, spawn):
        runner = ActionRunner(lambda: {})
        result = runner.run("open-config")
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 42)
        opened = Path(spawn.call_args.args[0][1])
        self.assertTrue(str(opened).endswith("lmdesktopplus") or "lmdesktopplus" in str(opened))

    @patch("lmdesktopplus.actions.executable", return_value="/usr/bin/loginctl")
    @patch("lmdesktopplus.preopt.run_capture", return_value=completed())
    def test_lock_uses_first_ok_scan(self, run_capture, _exe):
        result = ActionRunner(lambda: {}).lock()
        self.assertTrue(result["ok"])
        self.assertEqual(result["method"], "loginctl")
        self.assertEqual(run_capture.call_args[0][0], ["loginctl", "lock-session"])

    @patch("lmdesktopplus.actions.executable", return_value="/usr/bin/loginctl")
    @patch(
        "lmdesktopplus.preopt.run_capture",
        side_effect=subprocess.TimeoutExpired(["loginctl"], 5),
    )
    def test_lock_timeout_fails_soft(self, _run, _exe):
        result = ActionRunner(lambda: {}).lock()
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result.get("error", ""))


if __name__ == "__main__":
    unittest.main()
