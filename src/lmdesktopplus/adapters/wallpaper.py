"""Wallpaper catalog + apply — Cinnamon gsettings and/or hyprpaper.

@use levels: wallpaper_map/list are medium; apply is low use.
Preoptimized: try_run backend commands; one loop per catalog ingest.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import try_run
from ..util import app_data_dir, executable
from .base import command_error, dispatch_command

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".svg", ".webp"}
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_AUTO = object()
_APPLY_BACKENDS = frozenset({"cinnamon picture", "hyprpaper apply"})


def _default_package_dir() -> Path:
    # @use: low use — purpose: locate packaged wallpapers beside the Python package
    module_path = Path(__file__).resolve()
    candidates = (
        module_path.parents[2] / "assets" / "wallpapers",
        module_path.parents[3] / "assets" / "wallpapers",
        app_data_dir() / "assets" / "wallpapers",
    )
    return next((path for path in candidates if path.is_dir()), candidates[-1])


@register_fn(
    "wallpaper.slug",
    UseLevel.LOW,
    "Slugify wallpaper stem/suffix for stable catalog ids",
)
def _slug(value: str) -> str:
    # @use: low use — purpose: build wallpaper_map ids from filenames
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "wallpaper"


class WallpaperAdapter:
    """Hash-mapped wallpaper catalog with fail-soft multi-backend apply."""

    id = "wallpaper"

    def __init__(
        self,
        *,
        package_dir: Path | None = None,
        user_dir: Path | None = None,
        gsettings: str | None | object = _AUTO,
        hyprctl: str | None | object = _AUTO,
    ) -> None:
        self.package_dir = package_dir or _default_package_dir()
        self.user_dir = user_dir or app_data_dir() / "wallpapers"
        self.gsettings = executable("gsettings") if gsettings is _AUTO else gsettings
        self.hyprctl = executable("hyprctl") if hyprctl is _AUTO else hyprctl
        self._current_id: str | None = None

    def available(self) -> bool:
        return bool(self.wallpaper_map())

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: Appearance wallpaper panel summary
        wallpapers = self.wallpaper_map()
        return {
            "available": bool(wallpapers),
            "count": len(wallpapers),
            "current_id": self._current_id,
        }

    def wallpaper_map(self) -> dict[str, dict[str, Any]]:
        # @use: medium use — purpose: O(1) id→path catalog for picker + apply
        result: dict[str, dict[str, Any]] = {}
        seen_paths: set[Path] = set()
        # Two roots, each ingested with its own single-loop helper.
        self._ingest_directory("package", self.package_dir, result, seen_paths)
        self._ingest_directory("user", self.user_dir, result, seen_paths)
        return result

    def _ingest_directory(
        self,
        source: str,
        directory: Path,
        result: dict[str, dict[str, Any]],
        seen_paths: set[Path],
    ) -> None:
        # @use: medium use — purpose: one-loop scan of one wallpaper root
        try:
            paths = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
        except OSError:
            return
        for path in paths:
            entry = self._catalog_entry(source, path, seen_paths, result)
            entry is not None and result.update(entry)

    def _catalog_entry(
        self,
        source: str,
        path: Path,
        seen_paths: set[Path],
        result: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]] | None:
        # @use: medium use — purpose: map one file into a catalog id row
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return None
        # Prefer SVG source when a sibling raster exists in the package tree.
        skip_raster = (
            source == "package"
            and path.suffix.lower() in RASTER_SUFFIXES
            and path.with_suffix(".svg").is_file()
        )
        if skip_raster:
            return None
        try:
            resolved = path.resolve()
        except OSError:
            return None
        if resolved in seen_paths:
            return None
        seen_paths.add(resolved)
        wallpaper_id = f"{source}.{_slug(path.stem)}-{_slug(path.suffix[1:])}"
        wallpaper_id = (
            f"{wallpaper_id}-{len(result)}" if wallpaper_id in result else wallpaper_id
        )
        return {
            wallpaper_id: {
                "path": str(resolved),
                "thumb_path": f"/wallpaper-thumbs/{wallpaper_id}.png",
                "label": path.stem.replace("_", " ").replace("-", " ").title(),
                "source": source,
            }
        }

    def thumbnail_path(self, wallpaper_id: str) -> Path | None:
        # @use: medium use — purpose: serve picker thumbs from catalog entries
        entry = self.wallpaper_map().get(wallpaper_id)
        if not entry:
            return None
        wallpaper = Path(entry["path"])
        local_thumb = wallpaper.parent / "thumbs" / f"{wallpaper.stem}.png"
        return (
            local_thumb
            if local_thumb.is_file()
            else (
                (self.package_dir / "thumbs" / "placeholder.png")
                if (self.package_dir / "thumbs" / "placeholder.png").is_file()
                else None
            )
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: medium use — purpose: list/apply via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "list": lambda _payload: {"ok": True, "wallpapers": self.wallpaper_map()},
            "apply": self._apply_command,
        }

    def _apply_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: validate catalog id then multi-backend apply
        wallpaper_id = payload.get("id")
        catalog = self.wallpaper_map()
        return (
            command_error("invalid_argument", f"unknown wallpaper: {wallpaper_id}")
            if not isinstance(wallpaper_id, str) or wallpaper_id not in catalog
            else self._apply(wallpaper_id)
        )

    def _apply(self, wallpaper_id: str) -> dict[str, Any]:
        # @use: low use — purpose: install copy + cinnamon/hyprpaper backends
        source = Path(self.wallpaper_map()[wallpaper_id]["path"])
        destination = self._install_user_copy(source)
        if isinstance(destination, dict):
            return destination  # already an error payload

        results: list[dict[str, Any]] = []
        results.extend(self._apply_cinnamon(destination))
        hyprpaper_path = self._hyprpaper_path(destination)
        results.extend(self._apply_hyprpaper(hyprpaper_path))

        if not self._apply_succeeded(results):
            return {
                "ok": False,
                "error": (
                    "wallpaper commands failed"
                    if results
                    else "no compatible wallpaper backend available"
                ),
                "path": str(destination),
                "results": results,
            }
        self._current_id = wallpaper_id
        return {
            "ok": True,
            "id": wallpaper_id,
            "path": str(destination),
            "results": results,
            "hyprpaper_path": str(hyprpaper_path) if hyprpaper_path else None,
        }

    def _install_user_copy(self, source: Path) -> Path | dict[str, Any]:
        # @use: low use — purpose: copy catalog wallpaper into user wallpapers dir
        try:
            self.user_dir.mkdir(parents=True, exist_ok=True)
            destination = self.user_dir / source.name
            source.resolve() != destination.resolve() and shutil.copy2(source, destination)
            if source.suffix.lower() == ".svg":
                package_raster = source.with_suffix(".png")
                destination_raster = destination.with_suffix(".png")
                package_raster.is_file() and (
                    package_raster.resolve() != destination_raster.resolve()
                ) and shutil.copy2(package_raster, destination_raster)
            return destination
        except OSError as exc:
            return command_error("internal_error", f"could not install wallpaper: {exc}")

    def _apply_cinnamon(self, destination: Path) -> list[dict[str, Any]]:
        # @use: low use — purpose: Cinnamon picture-uri + zoom options
        if not self.gsettings:
            return []
        return [
            self._run(
                [
                    self.gsettings,
                    "set",
                    "org.cinnamon.desktop.background",
                    "picture-uri",
                    destination.as_uri(),
                ],
                "cinnamon picture",
            ),
            self._run(
                [
                    self.gsettings,
                    "set",
                    "org.cinnamon.desktop.background",
                    "picture-options",
                    "zoom",
                ],
                "cinnamon zoom",
            ),
        ]

    def _apply_hyprpaper(self, hyprpaper_path: Path | None) -> list[dict[str, Any]]:
        # @use: low use — purpose: hyprctl hyprpaper preload + wallpaper
        if not self.hyprctl or not hyprpaper_path:
            return []
        return [
            self._run(
                [self.hyprctl, "hyprpaper", "preload", str(hyprpaper_path)],
                "hyprpaper preload",
            ),
            self._run(
                [self.hyprctl, "hyprpaper", "wallpaper", f",{hyprpaper_path}"],
                "hyprpaper apply",
            ),
        ]

    @staticmethod
    def _apply_succeeded(results: list[dict[str, Any]]) -> bool:
        # @use: low use — purpose: require a real apply backend, not just setup
        return any(
            result["ok"] and result["backend"] in _APPLY_BACKENDS for result in results
        )

    def _hyprpaper_path(self, wallpaper: Path) -> Path | None:
        # @use: low use — purpose: hyprpaper needs a raster path
        if wallpaper.suffix.lower() in RASTER_SUFFIXES:
            return wallpaper
        raster = wallpaper.with_suffix(".png")
        return raster if raster.is_file() else None

    @staticmethod
    def _run(argv: list[str], label: str) -> dict[str, Any]:
        # @use: low use — purpose: one wallpaper backend command via try_run
        run = try_run(argv)
        if not run.launched:
            return {"ok": False, "backend": label, "error": run.error}
        return (
            {"ok": True, "backend": label}
            if run.ok
            else {
                "ok": False,
                "backend": label,
                "error": run.stderr.strip() or run.stdout.strip() or "command failed",
            }
        )
