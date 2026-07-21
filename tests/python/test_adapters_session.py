from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.session import SessionAdapter


class SessionAdapterTests(unittest.TestCase):
    def test_arm_hyprland_only_writes_one_shot_flag(self):
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
                result = SessionAdapter().command("arm_hyprland", {})

            flag = data_home / "lmdesktopplus" / "start-hyprland-once"
            self.assertEqual(
                result,
                {
                    "ok": True,
                    "armed": True,
                    "flag": str(flag),
                    "instructions": "Press Ctrl+Alt+F3, then log in.",
                },
            )
            self.assertEqual(flag.read_bytes(), b"")
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "unchanged")
            self.assertEqual(
                sorted(path.relative_to(tmp) for path in Path(tmp).rglob("*") if path.is_file()),
                [
                    Path("data/lmdesktopplus/start-hyprland-once"),
                    Path("keep-me"),
                ],
            )

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

        self.assertEqual(
            status,
            {
                "ok": True,
                "available": True,
                "hyprland_active": True,
                "cinnamon_active": False,
                "armed": True,
                "desktop": "Hyprland",
                "tty_hint": "Ctrl+Alt+F3",
            },
        )


if __name__ == "__main__":
    unittest.main()
