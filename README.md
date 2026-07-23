# LMDesktopPlus

A one-command **vapor//matrix** desktop rice for Linux Mint. Cinnamon stays the
default, daily-driver session; an optional Hyprland session is registered
alongside it for a mockup-faithful, tiling-window-manager experience. Both
sessions share the same palette, kitty/rofi/tmux/starship configs, and
wallpaper, so switching sessions at the login screen never feels like
switching themes.

[Original mockup preview](assets/preview/NeonRice-Vaporwave-Matrix-Rice.html)

> Screenshot/GIF coming soon — see `assets/preview/` for the original mockup
> this rice is based on.

## Hybrid model

| Session | Role | Notes |
|---------|------|-------|
| **Cinnamon** (default) | Daily Mint desktop | Themed via GTK CSS + wallpaper + `gsettings` (dark GTK/icon theme hints). Always installed; never requires Hyprland. |
| **Hyprland** (optional) | Mockup-faithful tiling rice | `hyprland.conf`, `waybar`, `rofi`, `kitty`, matching palette. Registered as a login-screen session **only if Hyprland is detected on `PATH`**. |

Both sessions consume:

- `palette/vapor-matrix.theme` — canonical palette/reference; app configs
  currently hard-code matching hex values across kitty, rofi, tmux, starship,
  GTK, and Hyprland/waybar.
- `packages/shared/` — kitty, rofi, tmux, starship, bash snippet, and GTK CSS
  configs, symlinked into `~/.config/...` (or `~/.tmux.conf`) so edits to the
  repo are picked up immediately without re-running the installer.

Hyprland support is **fail-soft**: if Hyprland isn't installed, `install.sh`
finishes the Cinnamon setup successfully and just logs a skip with a pointer
to [`docs/install-notes.md`](docs/install-notes.md) for manual setup.

## Quick start

```bash
git clone https://github.com/skyrailmaxima/LMDesktopPlus.git
cd LMDesktopPlus
./install.sh
# optional: also install Hyprland from distro packages
./install.sh --with-hyprland
# optional: allow community PPA only if you explicitly opt in
./install.sh --with-hyprland --allow-community-ppa
```

Then:

- Stay on **Cinnamon** for the themed daily-driver desktop (works out of the box).
- On Mint, start Hyprland from a TTY (`Ctrl+Alt+F3` → `./scripts/start-hyprland-tty.sh`)
  because LightDM often hides Wayland sessions — see [`docs/install-notes.md`](docs/install-notes.md).

Re-running `./install.sh` is idempotent — existing correct symlinks are left
alone. Existing **config targets** that would be replaced are backed up first
(see [Backups](#backups) below).

To roll back config changes made by this installer:

```bash
./uninstall.sh
```

See [Uninstall](#uninstall) for what is and is not removed.

## Flags

`install.sh` and its environment variables:

| Flag | Env equivalent | Effect |
|------|-----------------|--------|
| `--dry-run` | `DRY_RUN=1` | Print every planned action without touching the system. |
| `--cinnamon-only` | — | Skip Hyprland/waybar apt packages, config symlinks, and wayland-session registration. |
| `--with-hyprland` | — | Best-effort install Hyprland from **distro packages only**, then link configs/session. |
| `--allow-community-ppa` | — | With `--with-hyprland`: if distro packages fail, allow adding `ppa:cppiber/hyprland`. |
| `--hyprland-source=distro\|ppa\|existing` | — | Deterministic install source (`ppa` implies community PPA opt-in). |
| `--force` | `FORCE=1` | Continue installing on a non-Mint, non-Debian-family OS instead of refusing. |
| `-h`, `--help` | — | Print usage and exit. |

Examples:

```bash
./install.sh --dry-run
./install.sh --cinnamon-only
./install.sh --with-hyprland
./install.sh --with-hyprland --allow-community-ppa
./install.sh --with-hyprland --hyprland-source=existing
FORCE=1 ./install.sh
```

## What gets installed

1. Detects Linux Mint (warns and continues on Ubuntu/Debian-family, refuses
   otherwise unless `--force`/`FORCE=1`).
2. Installs shared apt packages (`kitty`, `rofi`, `tmux`, `btop`, `curl`,
   `wget`, `git`, `fonts-jetbrains-mono`), plus `waybar`/`swaybg` unless
   `--cinnamon-only`.
3. Fetches display fonts (DotGothic16, Zen Dots) into
   `~/.local/share/fonts/lmdesktopplus/`; failures are non-fatal and skipped
   with a warning (JetBrains Mono ships via apt).
4. Materializes the wallpaper and palette under
   `~/.local/share/lmdesktopplus/` and rasterizes the SVG wallpaper to PNG
   when a converter (`convert`, `rsvg-convert`, or `inkscape`) is available.
5. Symlinks shared configs into `~/.config/...` (kitty, rofi, tmux, starship,
   GTK 3/4 CSS, palette).
6. Applies Cinnamon `gsettings` (wallpaper, best-effort dark GTK/icon theme).
7. If Hyprland is detected: symlinks `hypr`/`waybar` configs and installs the
   wayland session `.desktop` file via `sudo` so it shows up at the login
   screen. If Hyprland is missing, this step is skipped with a log message.
8. Appends a marked snippet (`# LMDesktopPlus begin` / `... end`) to
   `~/.bashrc` — never touches the rest of your bashrc.

## Backups

Before replacing an existing **config target** (a file under `~/.config/...`,
`~/.tmux.conf`, or `~/.bashrc` when appending the snippet), `install.sh`
copies it to:

```
~/.lmdesktopplus-backup/<timestamp>/
```

Paths are preserved under that directory (for example,
`~/.config/kitty/kitty.conf` is backed up as
`~/.lmdesktopplus-backup/<timestamp>/.config/kitty/kitty.conf`).

**Not backed up:** wallpaper and palette copies under
`~/.local/share/lmdesktopplus/` are overwritten on each install; the Hyprland
wayland-session `.desktop` file under `/usr/share/wayland-sessions/` is
replaced without a home-directory backup.

Apt packages, fonts, and Cinnamon `gsettings` are applied during install;
those changes are outside the backup tree (see [Uninstall](#uninstall)).

## Uninstall

`./uninstall.sh` does **not** undo everything `install.sh` did. It:

- Restores known config paths from the **newest** backup under
  `~/.lmdesktopplus-backup/` (kitty, rofi, tmux, starship, GTK CSS, palette
  symlink, hypr/waybar configs, and `.bashrc` if one was backed up)
- Strips the `# LMDesktopPlus begin` / `# LMDesktopPlus end` block from
  `~/.bashrc`
- Removes LMDesktopPlus-owned config symlinks when there is no backup to
  restore
- Removes the Hyprland wayland-session file if it mentions LMDesktopPlus

It **leaves in place:**

- Apt packages installed by `install.sh` (including optional `waybar`/`swaybg`)
- Fonts under `~/.local/share/fonts/lmdesktopplus/`
- Wallpaper/palette under `~/.local/share/lmdesktopplus/`
- Cinnamon `gsettings` changes (wallpaper, GTK/icon theme hints)
- The backup tree under `~/.lmdesktopplus-backup/` (never deleted automatically)

## Repository layout

```
install.sh / uninstall.sh   Entrypoints
lib/                         common.sh, detect.sh, packages-apt.sh
palette/                     vapor-matrix.theme (canonical palette/reference)
packages/shared/             kitty, rofi, tmux, starship, bash, gtk-3.0/4.0
packages/cinnamon/           Cinnamon package README (docs-only in v1)
packages/hyprland/           hypr, waybar, wayland session .desktop
scripts/                     apply-cinnamon-gsettings.sh, fetch-fonts.sh
assets/                      wallpapers/, preview/ (original mockup)
docs/                        install-notes.md and design docs
tests/                       smoke-structure.sh
```

## Palette

Canonical file: [`palette/vapor-matrix.theme`](palette/vapor-matrix.theme)

| Token | Hex | Use |
|-------|-----|-----|
| mag | `#ff2e97` | Accent / active |
| pink | `#ff71ce` | Secondary accent |
| cyan | `#01cdfe` | Borders, highlights |
| mint | `#05ffa1` | Cursor / success |
| purple | `#b967ff` | Tertiary |
| grn | `#00ff70` | Matrix green |
| grn2 | `#8dffbe` | Soft green text |
| amber | `#ffcc44` | Warnings / labels |
| bg | `#05060a` | Base background |
| bg2 | `#0b0817` | Elevated panels |

## Testing

```bash
bash tests/smoke-structure.sh   # verifies expected files exist
./install.sh --dry-run          # verifies install plan without changing anything
```

## Known caveats

Hyprland support is best-effort on Linux Mint (there is no first-party apt
package). See [`docs/install-notes.md`](docs/install-notes.md) for
Hyprland-on-Mint installation guidance, manual session fallback, and font
troubleshooting.

## Non-goals (v1)

Pulsar editor theming, agent sandbox directories, a Nix flake, a live
matrix-rain wallpaper (static SVG/PNG only), and GNU Stow as the primary
installer are all out of scope for v1.

## License

[MIT](LICENSE) © 2026 skyrailmaxima
