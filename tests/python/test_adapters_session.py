from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.session import SessionAdapter


class SessionAdapterTests(unittest.TestCase):
    def test_arm_once_only_writes_one_shot_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_home = Path(tmp) / "data"
            unrelated = Path(tmp) / "keep-me"
            unrelated.write_text("unchanged", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "XDG_DATA_HOME": str(data_home),
                    "HYPRLAND_INSTANCE_SIGNATURE": "",
                    "XDG_CURRENT_DESKTOP": "X-Cinnamon",
                },
                clear=False,
            ):
                result = SessionAdapter().command("arm_once", {})

            flag = data_home / "lmdesktopplus" / "start-hyprland-once"
            self.assertTrue(result["ok"])
            self.assertTrue(result["armed"])
            self.assertEqual(result["lifecycle"], "armed")
            self.assertEqual(result["flag"], str(flag))
            self.assertIn("does not log out", result["instructions"])
            self.assertEqual(flag.read_bytes(), b"")
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "unchanged")

    def test_arm_hyprland_alias_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_home = Path(tmp)
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False):
                result = SessionAdapter().command("arm_hyprland", {})
            self.assertTrue(result["ok"])
            self.assertTrue((data_home / "lmdesktopplus" / "start-hyprland-once").is_file())

    def test_disarm_removes_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_home = Path(tmp)
            flag = data_home / "lmdesktopplus" / "start-hyprland-once"
            flag.parent.mkdir()
            flag.touch()
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False):
                result = SessionAdapter().command("disarm", {})
            self.assertTrue(result["ok"])
            self.assertFalse(result["armed"])
            self.assertFalse(flag.exists())

    def test_status_detects_active_desktop_and_armed_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_home = Path(tmp)
            flag = data_home / "lmdesktopplus" / "start-hyprland-once"
            flag.parent.mkdir()
            flag.touch()
            with patch.dict(
                os.environ,
                {
                    "XDG_DATA_HOME": str(data_home),
                    "HYPRLAND_INSTANCE_SIGNATURE": "instance-1",
                    "XDG_CURRENT_DESKTOP": "Hyprland",
                },
                clear=False,
            ):
                status = SessionAdapter().command("status", {})

        self.assertTrue(status["ok"])
        self.assertTrue(status["available"])
        self.assertTrue(status["hyprland_active"])
        self.assertTrue(status["armed"])
        self.assertEqual(status["lifecycle"], "active")
        self.assertEqual(status["desktop"], "Hyprland")
        self.assertIn("arm_once", status["capabilities"])


if __name__ == "__main__":
    unittest.main()
