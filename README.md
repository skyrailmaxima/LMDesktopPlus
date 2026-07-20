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
```

Then log out and back in:

- Pick **Cinnamon** for the themed daily-driver desktop (works out of the box).
- Pick **Hyprland** at the login greeter if it was detected and registered.

Re-running `./install.sh` is idempotent — existing correct symlinks are left
alone, and anything that would be overwritten is backed up first (see
[Backups](#backups) below).

To remove everything this installer changed:

```bash
./uninstall.sh
```

## Flags

`install.sh` and its environment variables:

| Flag | Env equivalent | Effect |
|------|-----------------|--------|
| `--dry-run` | `DRY_RUN=1` | Print every planned action (apt installs, symlinks, gsettings, bashrc append, session registration) without touching the system. |
| `--cinnamon-only` | — | Skip the Hyprland/waybar apt packages, config symlinks, and wayland-session registration entirely, even if Hyprland is present. |
| `--force` | `FORCE=1` | Continue installing on a non-Mint, non-Debian-family OS instead of refusing. |
| `-h`, `--help` | — | Print usage and exit. |

Examples:

```bash
./install.sh --dry-run              # see what would happen, change nothing
./install.sh --cinnamon-only        # Cinnamon-only box, skip Hyprland entirely
FORCE=1 ./install.sh                # override the Mint/Debian-family check
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

Any existing file that would be replaced is copied first to:

```
~/.lmdesktopplus-backup/<timestamp>/
```

`uninstall.sh` restores from the newest backup directory it can find,
removes the Hyprland wayland-session file if it was installed by this repo,
and strips the `# LMDesktopPlus begin/end` block from `~/.bashrc`. It never
deletes the backup tree itself.

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
