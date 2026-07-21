from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmdesktopplus.adapters.wallpaper import WallpaperAdapter


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class WallpaperAdapterTests(unittest.TestCase):
    def test_system_package_layout_scans_assets_beside_python_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package_root = root / "usr" / "lib" / "lmdesktopplus"
            package = package_root / "assets" / "wallpapers"
            package.mkdir(parents=True)
            (package / "vapor-matrix.svg").write_text("<svg/>", encoding="utf-8")
            installed_module = (
                package_root
                / "lmdesktopplus"
                / "adapters"
                / "wallpaper.py"
            )

            with (
                patch.dict(
                    os.environ,
                    {"XDG_DATA_HOME": str(root / "empty-data")},
                    clear=False,
                ),
                patch("lmdesktopplus.adapters.wallpaper.__file__", str(installed_module)),
            ):
                result = WallpaperAdapter(gsettings=None, hyprctl=None).command("list", {})

        self.assertIn("package.vapor-matrix-svg", result["wallpapers"])

    def test_installed_layout_scans_packaged_and_user_wallpaper_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data_home = root / "data"
            package = data_home / "lmdesktopplus" / "assets" / "wallpapers"
            user = data_home / "lmdesktopplus" / "wallpapers"
            package.mkdir(parents=True)
            user.mkdir(parents=True)
            (package / "vapor-matrix.svg").write_text("<svg/>", encoding="utf-8")
            (package / "vapor-matrix.png").write_bytes(b"full-size-png")
            (user / "custom.png").write_bytes(b"png")
            installed_module = Path(
                "/opt/lmdesktopplus/lmdesktopplus/adapters/wallpaper.py"
            )

            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}, clear=False),
                patch("lmdesktopplus.adapters.wallpaper.__file__", str(installed_module)),
            ):
                result = WallpaperAdapter(gsettings=None, hyprctl=None).command("list", {})

        self.assertEqual(
            set(result["wallpapers"]),
            {"package.vapor-matrix-svg", "user.custom-png"},
        )

    def test_list_scans_package_and_user_directories_with_stable_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            user = root / "user"
            thumbs = package / "thumbs"
            thumbs.mkdir(parents=True)
            user.mkdir()
            (package / "vapor-matrix.svg").write_text("<svg/>", encoding="utf-8")
            (thumbs / "vapor-matrix.png").write_bytes(b"thumb")
            (user / "Sun Set.JPG").write_bytes(b"wallpaper")
            (user / "notes.txt").write_text("ignore", encoding="utf-8")

            result = WallpaperAdapter(package_dir=package, user_dir=user).command("list", {})

        self.assertTrue(result["ok"])
        self.assertEqual(
            set(result["wallpapers"]),
            {"package.vapor-matrix-svg", "user.sun-set-jpg"},
        )
        package_entry = result["wallpapers"]["package.vapor-matrix-svg"]
        self.assertEqual(package_entry["label"], "Vapor Matrix")
        self.assertEqual(package_entry["thumb_path"], "/wallpaper-thumbs/package.vapor-matrix-svg.png")
        self.assertEqual(package_entry["source"], "package")

    @patch("lmdesktopplus.adapters.wallpaper.run_capture", return_value=completed())
    def test_apply_uses_cinnamon_gsettings_and_hyprpaper_for_raster(self, run_capture):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            user = root / "user"
            package.mkdir()
            (package / "city.png").write_bytes(b"png")
            adapter = WallpaperAdapter(
                package_dir=package,
                user_dir=user,
                gsettings="/usr/bin/gsettings",
                hyprctl="/usr/bin/hyprctl",
            )

            result = adapter.command("apply", {"id": "package.city-png"})

            installed = user / "city.png"
            self.assertEqual(installed.read_bytes(), b"png")
            self.assertTrue(result["ok"])
            self.assertEqual(result["path"], str(installed))
            self.assertEqual(
                [call.args[0] for call in run_capture.call_args_list],
                [
                    [
                        "/usr/bin/gsettings",
                        "set",
                        "org.cinnamon.desktop.background",
                        "picture-uri",
                        installed.as_uri(),
                    ],
                    [
                        "/usr/bin/gsettings",
                        "set",
                        "org.cinnamon.desktop.background",
                        "picture-options",
                        "zoom",
                    ],
                    ["/usr/bin/hyprctl", "hyprpaper", "preload", str(installed)],
                    ["/usr/bin/hyprctl", "hyprpaper", "wallpaper", f",{installed}"],
                ],
            )

    @patch("lmdesktopplus.adapters.wallpaper.run_capture", return_value=completed())
    def test_apply_svg_prefers_installer_raster_for_hyprpaper(self, run_capture):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            user = root / "user"
            package.mkdir()
            (package / "vapor-matrix.svg").write_text("<svg/>", encoding="utf-8")
            package_raster = package / "vapor-matrix.png"
            package_raster.write_bytes(b"full-size-png")
            adapter = WallpaperAdapter(
                package_dir=package,
                user_dir=user,
                gsettings=None,
                hyprctl="/usr/bin/hyprctl",
            )

            result = adapter.command("apply", {"id": "package.vapor-matrix-svg"})
            raster = user / "vapor-matrix.png"
            raster_bytes = raster.read_bytes()

        self.assertTrue(result["ok"])
        self.assertEqual(result["path"], str(user / "vapor-matrix.svg"))
        self.assertEqual(raster_bytes, b"full-size-png")
        self.assertEqual(
            [call.args[0] for call in run_capture.call_args_list],
            [
                ["/usr/bin/hyprctl", "hyprpaper", "preload", str(raster)],
                ["/usr/bin/hyprctl", "hyprpaper", "wallpaper", f",{raster}"],
            ],
        )

    def test_apply_rejects_unknown_id_without_running_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter = WallpaperAdapter(
                package_dir=Path(temp) / "package",
                user_dir=Path(temp) / "user",
                gsettings=None,
                hyprctl=None,
            )
            result = adapter.command("apply", {"id": "../../etc/passwd"})

        self.assertFalse(result["ok"])
        self.assertIn("unknown wallpaper", result["error"])

    @patch("lmdesktopplus.adapters.wallpaper.run_capture")
    def test_apply_fails_when_only_non_apply_setup_command_succeeds(self, run_capture):
        run_capture.side_effect = [
            completed(stderr="no schema", returncode=1),
            completed(),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"
            package.mkdir()
            (package / "city.png").write_bytes(b"png")
            result = WallpaperAdapter(
                package_dir=package,
                user_dir=root / "user",
                gsettings="/usr/bin/gsettings",
                hyprctl=None,
            ).command("apply", {"id": "package.city-png"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "wallpaper commands failed")


if __name__ == "__main__":
    unittest.main()
