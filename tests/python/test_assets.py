from __future__ import annotations

import unittest
from importlib.resources import files

from lmdesktopplus.assets import ICON_MAP, AssetCatalog


class AssetCatalogTests(unittest.TestCase):
    EXPECTED_IDS = {
        "audio.volume",
        "audio.mute",
        "display.brightness",
        "bluetooth",
        "notify",
        "update",
        "session.hyprland",
        "session.cinnamon",
        "wallpaper",
        "clipboard",
        "camera",
        "vpn",
        "usb",
        "power",
    }

    def test_icon_map_loaded_from_manifest(self):
        self.assertEqual(set(ICON_MAP.keys()), self.EXPECTED_IDS)

    def test_manifest_entries_have_file_and_label(self):
        for icon_id, entry in ICON_MAP.items():
            self.assertIn("file", entry, icon_id)
            self.assertIn("label", entry, icon_id)
            self.assertTrue(entry["file"].endswith(".svg"), icon_id)

    def test_svg_files_exist_and_valid(self):
        icons_dir = files("lmdesktopplus").joinpath("static", "icons")
        for entry in ICON_MAP.values():
            svg = icons_dir.joinpath(entry["file"])
            data = svg.read_bytes()
            text = data.decode("utf-8")
            self.assertLessEqual(len(data), 1024, entry["file"])
            self.assertIn('viewBox="0 0 24 24"', text, entry["file"])
            self.assertIn("currentColor", text, entry["file"])

    def test_asset_catalog_exposes_icons(self):
        payload = AssetCatalog().as_dict()
        self.assertEqual(set(payload["icons"]), self.EXPECTED_IDS)


if __name__ == "__main__":
    unittest.main()
