from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.actions import (
    ACTION_HANDLERS,
    LAUNCH_HANDLERS,
    ActionRunner,
    wrap_in_terminal,
)


class WrapInTerminalTests(unittest.TestCase):
    @patch("lmdesktopplus.actions.first_executable", return_value="/usr/bin/kitty")
    def test_kitty_hold_spreads_argv(self, _first):
        self.assertEqual(
            wrap_in_terminal(["tmux", "attach"], hold=True),
            ["/usr/bin/kitty", "--hold", "tmux", "attach"],
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


if __name__ == "__main__":
    unittest.main()
