from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..util import app_data_dir, executable, run_capture

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".svg", ".webp"}
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_AUTO = object()


def _default_package_dir() -> Path:
    module_path = Path(__file__).resolve()
    candidates = (
        module_path.parents[2] / "assets" / "wallpapers",
        module_path.parents[3] / "assets" / "wallpapers",
        app_data_dir() / "assets" / "wallpapers",
    )
    return next((path for path in candidates if path.is_dir()), candidates[-1])


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "wallpaper"


class WallpaperAdapter:
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
        wallpapers = self.wallpaper_map()
        return {
            "available": bool(wallpapers),
            "count": len(wallpapers),
            "current_id": self._current_id,
        }

    def wallpaper_map(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        seen_paths: set[Path] = set()
        for source, directory in (("package", self.package_dir), ("user", self.user_dir)):
            try:
                paths = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
            except OSError:
                continue
            for path in paths:
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue
                if (
                    source == "package"
                    and path.suffix.lower() in RASTER_SUFFIXES
                    and path.with_suffix(".svg").is_file()
                ):
                    continue
                resolved = path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                wallpaper_id = f"{source}.{_slug(path.stem)}-{_slug(path.suffix[1:])}"
                if wallpaper_id in result:
                    wallpaper_id = f"{wallpaper_id}-{len(result)}"
                result[wallpaper_id] = {
                    "path": str(resolved),
                    "thumb_path": f"/wallpaper-thumbs/{wallpaper_id}.png",
                    "label": path.stem.replace("_", " ").replace("-", " ").title(),
                    "source": source,
                }
        return result

    def thumbnail_path(self, wallpaper_id: str) -> Path | None:
        entry = self.wallpaper_map().get(wallpaper_id)
        if not entry:
            return None
        wallpaper = Path(entry["path"])
        local_thumb = wallpaper.parent / "thumbs" / f"{wallpaper.stem}.png"
        if local_thumb.is_file():
            return local_thumb
        placeholder = self.package_dir / "thumbs" / "placeholder.png"
        return placeholder if placeholder.is_file() else None

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name == "list":
            return {"ok": True, "wallpapers": self.wallpaper_map()}
        if name != "apply":
            return {"ok": False, "error": f"unknown wallpaper command: {name}"}
        wallpaper_id = payload.get("id")
        if not isinstance(wallpaper_id, str) or wallpaper_id not in self.wallpaper_map():
            return {"ok": False, "error": f"unknown wallpaper: {wallpaper_id}"}
        return self._apply(wallpaper_id)

    def _apply(self, wallpaper_id: str) -> dict[str, Any]:
        source = Path(self.wallpaper_map()[wallpaper_id]["path"])
        try:
            self.user_dir.mkdir(parents=True, exist_ok=True)
            destination = self.user_dir / source.name
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            if source.suffix.lower() == ".svg":
                package_raster = source.with_suffix(".png")
                destination_raster = destination.with_suffix(".png")
                if package_raster.is_file() and (
                    package_raster.resolve() != destination_raster.resolve()
                ):
                    shutil.copy2(package_raster, destination_raster)
        except OSError as exc:
            return {"ok": False, "error": f"could not install wallpaper: {exc}"}

        results: list[dict[str, Any]] = []
        if self.gsettings:
            results.append(
                self._run(
                    [
                        self.gsettings,
                        "set",
                        "org.cinnamon.desktop.background",
                        "picture-uri",
                        destination.as_uri(),
                    ],
                    "cinnamon picture",
                )
            )
            results.append(
                self._run(
                    [
                        self.gsettings,
                        "set",
                        "org.cinnamon.desktop.background",
                        "picture-options",
                        "zoom",
                    ],
                    "cinnamon zoom",
                )
            )

        hyprpaper_path = self._hyprpaper_path(destination)
        if self.hyprctl and hyprpaper_path:
            results.append(
                self._run(
                    [self.hyprctl, "hyprpaper", "preload", str(hyprpaper_path)],
                    "hyprpaper preload",
                )
            )
            results.append(
                self._run(
                    [self.hyprctl, "hyprpaper", "wallpaper", f",{hyprpaper_path}"],
                    "hyprpaper apply",
                )
            )

        applied = any(
            result["ok"]
            and result["backend"] in {"cinnamon picture", "hyprpaper apply"}
            for result in results
        )
        if not applied:
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

    def _hyprpaper_path(self, wallpaper: Path) -> Path | None:
        if wallpaper.suffix.lower() in RASTER_SUFFIXES:
            return wallpaper
        raster = wallpaper.with_suffix(".png")
        return raster if raster.is_file() else None

    @staticmethod
    def _run(argv: list[str], label: str) -> dict[str, Any]:
        try:
            completed = run_capture(argv)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "backend": label, "error": str(exc)}
        if completed.returncode != 0:
            return {
                "ok": False,
                "backend": label,
                "error": completed.stderr.strip() or completed.stdout.strip() or "command failed",
            }
        return {"ok": True, "backend": label}
