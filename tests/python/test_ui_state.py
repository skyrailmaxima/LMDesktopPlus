from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lmdesktopplus.ui_state import (
    DEFAULT_HEIGHT,
    DEFAULT_SCENE,
    DEFAULT_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    UiStateStore,
    valid_scene,
)


class UiStateStoreTests(unittest.TestCase):
    def _store(self) -> UiStateStore:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return UiStateStore(Path(tmp.name) / "ui-state.json")

    def test_defaults_when_missing(self):
        store = self._store()
        state = store.get()
        self.assertEqual(state["scene"], DEFAULT_SCENE)
        self.assertEqual(state["window"]["width"], DEFAULT_WIDTH)
        self.assertEqual(state["window"]["height"], DEFAULT_HEIGHT)
        self.assertFalse(state["window"]["maximized"])

    def test_set_scene_persists_and_reloads(self):
        store = self._store()
        self.assertEqual(store.set_scene("monitor"), "monitor")
        reloaded = UiStateStore(store.path)
        self.assertEqual(reloaded.scene(), "monitor")

    def test_invalid_scene_is_ignored(self):
        store = self._store()
        store.set_scene("settings")
        self.assertEqual(store.set_scene("../etc/passwd"), "settings")
        self.assertEqual(store.set_scene("UPPER"), "settings")

    def test_window_geometry_clamped_and_persisted(self):
        store = self._store()
        saved = store.set_window(10, 10, True)  # below minimums
        self.assertEqual(saved["width"], MIN_WIDTH)
        self.assertEqual(saved["height"], MIN_HEIGHT)
        self.assertTrue(saved["maximized"])
        reloaded = UiStateStore(store.path)
        self.assertEqual(reloaded.get()["window"]["width"], MIN_WIDTH)
        self.assertTrue(reloaded.get()["window"]["maximized"])

    def test_corrupt_file_falls_back_to_defaults(self):
        store = self._store()
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("{ not json", encoding="utf-8")
        fresh = UiStateStore(store.path)
        self.assertEqual(fresh.scene(), DEFAULT_SCENE)

    def test_normalizes_partial_window_dict(self):
        store = self._store()
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text(json.dumps({"window": {"width": 900}}), encoding="utf-8")
        fresh = UiStateStore(store.path)
        window = fresh.get()["window"]
        self.assertEqual(window["width"], 900)
        self.assertEqual(window["height"], DEFAULT_HEIGHT)

    def test_valid_scene_helper(self):
        self.assertTrue(valid_scene("desktop"))
        self.assertTrue(valid_scene("ui-kit_2"))
        self.assertFalse(valid_scene("Desktop"))
        self.assertFalse(valid_scene("9start"))
        self.assertFalse(valid_scene(""))
        self.assertFalse(valid_scene(None))


if __name__ == "__main__":
    unittest.main()
