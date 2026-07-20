# Cinnamon package (v1 hybrid)

LMDesktopPlus targets a **hybrid session model**: Cinnamon remains the default Linux Mint desktop, while an optional Hyprland session can be registered for a mockup-faithful rice. Both paths share `palette/vapor-matrix.theme` and configs under `packages/shared/`.

## v1 scope

v1 does **not** ship a full custom Cinnamon theme tarball (Metacity/Cinnamon window decorations, panel applet styling, etc.). Instead, install applies:

| Layer | Source | Notes |
|-------|--------|-------|
| Wallpaper | `assets/wallpapers/vapor-matrix.svg` copied to `~/.local/share/lmdesktopplus/wallpapers/` | Set via `scripts/apply-cinnamon-gsettings.sh` |
| GTK look | `packages/shared/gtk-3.0/gtk.css` and `gtk-4.0/gtk.css` | Symlinked into `~/.config/` by `install.sh` |
| GTK / icon hints | gsettings | `Mint-Y-Dark` + `Papirus-Dark` when available on the system |
| Apps | `packages/shared/` | kitty, rofi, tmux, starship |

A post-v1 release may add `packages/cinnamon/themes/` with a dedicated Cinnamon + Metacity theme aligned to the vapor//matrix palette.

## gsettings applied

`install.sh` calls `scripts/apply-cinnamon-gsettings.sh` with the materialized wallpaper path (under `~/.local/share/lmdesktopplus/wallpapers/` or the repo asset during development).

| Key | Value |
|-----|-------|
| `org.cinnamon.desktop.background picture-uri` | `file://<wallpaper>` |
| `org.cinnamon.desktop.background picture-options` | `zoom` |
| `org.cinnamon.desktop.interface gtk-theme` | `Mint-Y-Dark` (best-effort) |
| `org.cinnamon.desktop.interface icon-theme` | `Papirus-Dark` (best-effort) |

Use `DRY_RUN=1` to print the wallpaper path without writing settings.

## Manual theme tweaks (optional)

If Mint-Y-Dark or Papirus-Dark is missing, install still succeeds; pick any dark GTK and icon theme in **System Settings → Themes** that matches your install. When a full Cinnamon theme lands, this README will document panel and window-decoration keys; until then, rely on GTK CSS and the vapor-matrix wallpaper for the vapor//matrix look.
