# Install notes

Detailed caveats for running LMDesktopPlus on Linux Mint, especially around
the optional Hyprland session and fonts. Start with the [README](../README.md)
quick start; this document covers the rough edges.

## Hyprland on Linux Mint

Linux Mint (and Ubuntu, which it tracks) often does **not** ship an official
Hyprland apt package. `install.sh` only registers the Hyprland session and
links `packages/hyprland/` configs when it finds `Hyprland` (or `hyprland`) on
`PATH`. If Hyprland isn't found, the Cinnamon path still completes
successfully.

### Installing Hyprland with this repo

```bash
# Distro / universe packages only (default). Never adds a third-party PPA.
./install.sh --with-hyprland

# Explicit community PPA opt-in (ppa:cppiber/hyprland) if distro packages fail.
./install.sh --with-hyprland --allow-community-ppa

# Deterministic source selection
./install.sh --with-hyprland --hyprland-source=distro
./install.sh --with-hyprland --hyprland-source=ppa      # implies --allow-community-ppa
./install.sh --with-hyprland --hyprland-source=existing # require already on PATH
```

`scripts/install-hyprland-mint.sh` decision flow:

1. If Hyprland is already on `PATH` → done.
2. Try distro/`universe` packages (`hyprland` + `xdg-desktop-portal-hyprland`, then compositor-only retry).
3. On failure:
   - with `--allow-community-ppa` / `--hyprland-source=ppa` → add `ppa:cppiber/hyprland` and retry
   - otherwise → print manual options and leave Cinnamon install intact

Apt failures print captured stderr (nothing is swallowed with `2>/dev/null`).

> **Note:** `ppa:cppiber/hyprland` is a **community** PPA (not Canonical or
> official Hyprland packaging). Review it before enabling on production boxes.

### Mint start path: TTY (not the greeter)

LightDM on Mint frequently hides `/usr/share/wayland-sessions/`. After install:

1. `./install.sh --with-hyprland` (add `--allow-community-ppa` only if you opt in)
2. `Ctrl+Alt+F3` → log in
3. `./scripts/start-hyprland-tty.sh`

Or use `./switch.sh` from a clone: it installs (distro-only by default), then
either starts Hyprland on a TTY or arms a one-shot bashrc handoff from Cinnamon.

The TTY launcher:

- refuses to start inside an existing graphical session
- warns unless stdin/`tty` look like a real VT
- requires a usable `XDG_RUNTIME_DIR` (defaults to `/run/user/$(id -u)`)
- sets minimal session identity (`XDG_SESSION_TYPE/CLASS/DESKTOP`)
- appends a startup log to `~/.local/state/lmdesktopplus/hyprland-start.log`

### Manual fallback without the community PPA

```bash
# After installing Hyprland yourself:
./install.sh
# or from a TTY:
./scripts/start-hyprland-tty.sh
```

### If `sudo cp` for the session file fails

```bash
sudo cp packages/hyprland/sessions/lmdesktopplus-hyprland.desktop \
  /usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop
```

### Wallpaper: PNG vs SVG fallback

`hyprpaper.conf` expects a rasterized PNG at
`~/.local/share/lmdesktopplus/wallpapers/vapor-matrix.png`. `install.sh`
tries `convert`, then `rsvg-convert`, then `inkscape`. If none succeed it
falls back to `swaybg` with the SVG.

### Fonts

JetBrains Mono comes from apt (`fonts-jetbrains-mono`). DotGothic16 / Zen Dots
are fetched best-effort by `scripts/fetch-fonts.sh` into
`~/.local/share/fonts/lmdesktopplus/`.

### Uninstall

`./uninstall.sh` restores backed-up configs from the newest
`~/.lmdesktopplus-backup/<timestamp>/` tree, removes the LMDesktopPlus bashrc
marker block, and removes the wayland session desktop file when present. It
does **not** remove apt packages or the community PPA if you added one.
