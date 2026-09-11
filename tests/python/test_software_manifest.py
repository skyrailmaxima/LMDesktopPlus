"""Validate the canonical software manifest and its generated package fields."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import json

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PY = ROOT / "packaging" / "manifest.py"
ORIGINS_JSON = ROOT / "packaging" / "freebsd" / "pkg-origins.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("lmdp_manifest", MANIFEST_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SoftwareManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_module()
        cls.components = cls.m.load()

    def test_manifest_passes_self_check(self):
        self.assertEqual(self.m._check(self.components), [])

    def test_ids_unique(self):
        ids = [c["id"] for c in self.components]
        self.assertEqual(len(ids), len(set(ids)))

    def test_debian_control_fields_match_expected(self):
        # Locks the generated control so the .deb stays byte-stable across the
        # manifest refactor.
        self.assertEqual(
            self.m.debian_field(self.components, "Depends"),
            "python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, "
            "gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0, network-manager",
        )
        self.assertEqual(
            self.m.debian_field(self.components, "Recommends"),
            "kitty, rofi, tmux, btop, playerctl, bubblewrap",
        )
        self.assertEqual(
            self.m.debian_field(self.components, "Suggests"),
            "hyprland, waybar, bluez, starship, policykit-1, grim, slurp, "
            "wl-clipboard, xclip, libnotify-bin, mintupdate, cups-client, "
            "system-config-printer, swayidle, mpvpaper",
        )

    def test_metapackage_is_superset_of_main_fields(self):
        meta = set(self.m.debian_metapackage_depends(self.components))
        for field in ("Depends", "Recommends", "Suggests"):
            entries = [e.strip() for e in self.m.debian_field(self.components, field).split(",")]
            for entry in entries:
                self.assertIn(entry, meta, f"{entry} missing from metapackage depends")

    def test_metapackage_includes_rice_and_fonts(self):
        meta = set(self.m.debian_metapackage_depends(self.components))
        for pkg in ("curl", "wget", "git", "swaybg", "fonts-jetbrains-mono"):
            self.assertIn(pkg, meta)

    def test_ofl_fonts_carry_no_distro_package(self):
        ofl = [c for c in self.components if c.get("source") == "ofl-fetch"]
        self.assertTrue(ofl)
        for comp in ofl:
            self.assertIsNone(comp.get("debian"))
            self.assertIsNone(comp.get("freebsd"))

    def test_freebsd_excludes_linux_only_peers(self):
        bsd = set(self.m.freebsd_packages(self.components))
        for linux_only in ("network-manager", "bubblewrap", "bluez", "mintupdate"):
            self.assertNotIn(linux_only, bsd)

    def test_freebsd_origins_cover_every_pkg(self):
        raw = json.loads(ORIGINS_JSON.read_text(encoding="utf-8"))
        origins = raw.get("origins", raw)
        # Must not raise (every FreeBSD pkg has an origin mapping).
        lines = self.m.freebsd_run_depends(self.components, origins)
        self.assertEqual(len(lines), len(self.m.freebsd_packages(self.components)))
        self.assertIn("webkit2-gtk>0:www/webkit2-gtk@40", lines)
        self.assertIn("kitty>0:x11/kitty", lines)
        self.assertIn("py-gobject3>0:devel/py-gobject3", lines)

    def test_freebsd_run_depends_raises_on_missing_origin(self):
        with self.assertRaises(KeyError):
            self.m.freebsd_run_depends(self.components, {})


if __name__ == "__main__":
    unittest.main()
