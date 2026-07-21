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


if __name__ == "__main__":
    unittest.main()
