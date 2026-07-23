from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from lmdesktopplus.adapters.notifications import NotificationsAdapter, sanitize_notify_text


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class SanitizeTests(unittest.TestCase):
    def test_sanitize_strips_controls_and_caps(self):
        self.assertEqual(sanitize_notify_text("hello\x00world", 20), "helloworld")
        self.assertEqual(len(sanitize_notify_text("x" * 200, 40)), 40)


class NotificationsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"behavior": {"do_not_disturb": False}}

        def get_settings():
            return self.settings

        def update_settings(patch):
            if "behavior" in patch:
                self.settings["behavior"].update(patch["behavior"])
            return self.settings

        self.get_settings = get_settings
        self.update_settings = update_settings

    def test_snapshot_reports_local_dnd_when_notify_send_missing(self):
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send=None,
            gsettings=None,
        )
        self.assertEqual(
            adapter.snapshot(),
            {
                "available": True,
                "can_send": False,
                "dnd": False,
                "dnd_backend": "local",
            },
        )

    @patch("lmdesktopplus.adapters.notifications.run_capture")
    def test_snapshot_reads_cinnamon_dnd(self, run_capture):
        run_capture.return_value = completed("false\n")
        self.settings["behavior"]["do_not_disturb"] = False
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send="/usr/bin/notify-send",
            gsettings="/usr/bin/gsettings",
        )
        snap = adapter.snapshot()
        self.assertTrue(snap["can_send"])
        self.assertTrue(snap["dnd"])
        self.assertEqual(snap["dnd_backend"], "cinnamon")
        run_capture.assert_called_with(
            [
                "/usr/bin/gsettings",
                "get",
                "org.cinnamon.desktop.notifications",
                "display-notifications",
            ],
            timeout=3,
        )

    @patch("lmdesktopplus.adapters.notifications.run_capture", return_value=completed())
    def test_send_test_skips_when_dnd(self, run_capture):
        self.settings["behavior"]["do_not_disturb"] = True
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send="/usr/bin/notify-send",
            gsettings=None,
        )
        result = adapter.command("send_test", {})
        self.assertEqual(result, {"ok": True, "skipped": True, "reason": "do_not_disturb"})
        run_capture.assert_not_called()

    @patch("lmdesktopplus.adapters.notifications.run_capture", return_value=completed())
    def test_send_test_uses_notify_send(self, run_capture):
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send="/usr/bin/notify-send",
            gsettings=None,
        )
        result = adapter.command("send_test", {"title": "Hi", "body": "There"})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(
            run_capture.call_args.args[0],
            [
                "/usr/bin/notify-send",
                "-a",
                "LMDesktopPlus",
                "-u",
                "normal",
                "--",
                "Hi",
                "There",
            ],
        )

    @patch("lmdesktopplus.adapters.notifications.run_capture", return_value=completed())
    def test_set_dnd_updates_settings_and_gsettings(self, run_capture):
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send="/usr/bin/notify-send",
            gsettings="/usr/bin/gsettings",
        )
        result = adapter.command("set_dnd", {"enabled": True})
        self.assertEqual(result["ok"], True)
        self.assertTrue(self.settings["behavior"]["do_not_disturb"])
        self.assertEqual(
            run_capture.call_args.args[0],
            [
                "/usr/bin/gsettings",
                "set",
                "org.cinnamon.desktop.notifications",
                "display-notifications",
                "false",
            ],
        )

    def test_unknown_command_rejected(self):
        adapter = NotificationsAdapter(
            settings_get=self.get_settings,
            settings_update=self.update_settings,
            notify_send=None,
            gsettings=None,
        )
        self.assertFalse(adapter.command("history", {})["ok"])


if __name__ == "__main__":
    unittest.main()
