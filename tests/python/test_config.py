from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lmdesktopplus.config import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_validation_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore(path)
            value = store.update({"appearance": {"opacity": 999, "accent": "invalid"}, "behavior": {"poll_interval_ms": 10}})
            self.assertEqual(value["appearance"]["opacity"], 100)
            self.assertEqual(value["appearance"]["accent"], "mag")
            self.assertEqual(value["behavior"]["poll_interval_ms"], 500)
            reloaded = SettingsStore(path).get()
            self.assertEqual(reloaded, value)

    def test_customization_defaults_are_inert(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            cust = store.get()["customization"]
            self.assertEqual(cust["greeting"]["messages"], ["VAPOR//MATRIX"])
            self.assertEqual(cust["greeting"]["mode"], "static")
            self.assertEqual(cust["greeting"]["rotate_seconds"], 0)
            self.assertEqual(cust["text"], {})
            self.assertEqual(cust["layouts"], {})

    def test_greeting_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            value = store.update({"customization": {"greeting": {
                "messages": ["  hi there  ", "", 42, "x" * 500],
                "mode": "bogus",
                "rotate_seconds": 2,
            }}})
            greeting = value["customization"]["greeting"]
            # blanks/non-strings dropped, surrounding whitespace trimmed, length capped
            self.assertEqual(greeting["messages"][0], "hi there")
            self.assertEqual(len(greeting["messages"]), 2)
            self.assertLessEqual(len(greeting["messages"][1]), 120)
            self.assertEqual(greeting["mode"], "static")  # invalid -> default
            self.assertEqual(greeting["rotate_seconds"], 5)  # 2 -> clamped up to 5

    def test_greeting_empty_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            value = store.update({"customization": {"greeting": {"messages": ["", "   "]}}})
            self.assertEqual(value["customization"]["greeting"]["messages"], ["VAPOR//MATRIX"])
            v2 = store.update({"customization": {"greeting": {"mode": "random", "rotate_seconds": 99999}}})
            self.assertEqual(v2["customization"]["greeting"]["mode"], "random")
            self.assertEqual(v2["customization"]["greeting"]["rotate_seconds"], 3600)

    def test_text_overrides_whitelisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            value = store.update({"customization": {"text": {
                "desktop.title": "  My Rig  ",
                "desktop.subtitle": "hello",
                "monitor.title": "Vitals",
                "bogus.title": "nope",        # unknown scene -> dropped
                "desktop.badfield": "nope",   # unknown field -> dropped
                "malformed": "nope",          # no dot -> dropped
                "apps.title": "   ",          # blank -> dropped
            }}})
            text = value["customization"]["text"]
            self.assertEqual(text["desktop.title"], "My Rig")
            self.assertEqual(text["monitor.title"], "Vitals")
            self.assertNotIn("bogus.title", text)
            self.assertNotIn("desktop.badfield", text)
            self.assertNotIn("malformed", text)
            self.assertNotIn("apps.title", text)

    def test_layout_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp) / "settings.json")
            value = store.update({"customization": {"layouts": {
                "desktop": {
                    "order": ["cpu", "memory", "cpu", "BAD id", 7],  # dedup + drop invalid
                    "hidden": ["gpu"],
                    "views": {"cpu": "sparkline", "memory": "BAD", "x!": "kpi"},
                },
                "notascene": {"order": ["cpu"]},  # unknown scene dropped
            }}})
            layouts = value["customization"]["layouts"]
            self.assertEqual(layouts["desktop"]["order"], ["cpu", "memory"])
            self.assertEqual(layouts["desktop"]["hidden"], ["gpu"])
            self.assertEqual(layouts["desktop"]["views"], {"cpu": "sparkline"})
            self.assertNotIn("notascene", layouts)


if __name__ == "__main__":
    unittest.main()
