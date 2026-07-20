# Install notes

Detailed caveats for running LMDesktopPlus on Linux Mint, especially around
the optional Hyprland session and fonts. Start with the [README](../README.md)
quick start; this document covers the rough edges.

## Hyprland on Linux Mint

Linux Mint (and Ubuntu, which it tracks) does **not** ship an official
Hyprland apt package in most releases. `install.sh` only registers the
Hyprland session and links `packages/hyprland/` configs when it finds
`Hyprland` (or `hyprland`) on `PATH` — it never tries to compile or install
Hyprland itself. If Hyprland isn't found, the Cinnamon path still completes
successfully; you'll just see a log line pointing back here.

### Getting Hyprland onto Mint

There is no single command that works on every Mint/Ubuntu release. In
rough order of preference:

1. **Check if a PPA/repo exists for your base Ubuntu release.** Hyprland
   moves fast and packaging lags; search for a Hyprland PPA or a
   community repo matching your Mint's Ubuntu base (`lsb_release -a`, or
   check `/etc/os-release` for `UBUNTU_CODENAME`). Add it, then:

   ```bash
   sudo apt update
   sudo apt install hyprland
   ```

2. **Build from source** (most reliable, more work). Follow the official
   Hyprland wiki build instructions for your Ubuntu base version — you'll
   need a recent `wlroots`, `meson`, `ninja`, and a handful of `-dev`
   packages. This is the path most Mint users will end up on for now.

3. **Distro-hop for the Hyprland session only** is out of scope for this
   repo; LMDesktopPlus assumes Mint stays the base OS.

Once `Hyprland` (or `hyprland`) resolves on `PATH`, re-run:

```bash
./install.sh
```

and the installer will pick it up: it links `packages/hyprland/hypr/` and
`packages/hyprland/waybar/` configs, and installs the wayland session
`.desktop` file (via `sudo cp`) so **LMDesktopPlus Hyprland** appears at your
login greeter alongside Cinnamon.

### If `sudo cp` for the session file fails

Installing `packages/hyprland/sessions/lmdesktopplus-hyprland.desktop` to
`/usr/share/wayland-sessions/` requires `sudo`. If that step fails (no sudo
access, read-only `/usr`, etc.), the installer logs a warning and continues;
copy it manually:

```bash
sudo cp packages/hyprland/sessions/lmdesktopplus-hyprland.desktop \
  /usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop
```

Then log out; the session should appear in your display manager's session
picker.

### Manual fallback: launching Hyprland without a registered session

If you'd rather not touch `/usr/share/wayland-sessions/` at all, you can
still use the themed configs from a TTY:

```bash
# From a text console (Ctrl+Alt+F3, log in), with hypr configs already
# symlinked by install.sh:
Hyprland
```

`hyprland.conf` expects `waybar` and either `hyprpaper` or `swaybg` to be on
`PATH`. `install.sh` installs `waybar` and `swaybg` via apt unless you passed
`--cinnamon-only` (that flag skips the optional Hyprland apt packages
entirely, independent of whether Hyprland is on `PATH`). If you used
`--cinnamon-only`, install them manually:

```bash
sudo apt install waybar swaybg
```

### Wallpaper: PNG vs SVG fallback

`hyprpaper.conf` expects a rasterized PNG at
`~/.local/share/lmdesktopplus/wallpapers/vapor-matrix.png`. `install.sh`
tries `convert` (ImageMagick), then `rsvg-convert`, then `inkscape`, in that
order, to produce it. If none of those are installed (or all fail — e.g. a
locked-down ImageMagick `policy.xml`), no PNG is created and the installer
warns you.

To fix it, either:

- Install one of the converters and re-run `./install.sh`:

  ```bash
  sudo apt install librsvg2-bin   # provides rsvg-convert, lightweight
  ```

- Or switch Hyprland to `swaybg`, which can render the SVG directly. In
  `packages/hyprland/hypr/hyprland.conf`, comment out the `hyprpaper`
  `exec-once` line and uncomment the `swaybg` one, pointing at
  `~/.local/share/lmdesktopplus/wallpapers/vapor-matrix.svg`.

Cinnamon does not have this problem: `apply-cinnamon-gsettings.sh` falls
back to the SVG directly via `gsettings` if no PNG exists.

## Fonts

`scripts/fetch-fonts.sh` downloads **DotGothic16** and **Zen Dots** (both
Google Fonts, OFL-licensed) into `~/.local/share/fonts/lmdesktopplus/` and
refreshes the font cache with `fc-cache`. **JetBrains Mono** is not handled
here — it ships via the `fonts-jetbrains-mono` apt package installed earlier
in `install.sh`.

### Troubleshooting

- **Offline / fetch fails**: font downloads use `curl` (preferred) or
  `wget` with a short timeout. Failures are logged as warnings and are
  **non-fatal** — the rest of the install continues, and kitty/rofi/waybar
  fall back to whatever font resolves (usually a generic sans/mono). Re-run
  `./install.sh` (or just `bash scripts/fetch-fonts.sh`) once you have
  network access; already-downloaded fonts are skipped unless `FORCE=1`.
- **Fonts downloaded but not showing up**: run `fc-cache -f
  ~/.local/share/fonts/lmdesktopplus` manually, then restart the app (kitty,
  rofi) or re-log-in for Cinnamon/GTK to notice new fonts.
- **Neither `curl` nor `wget` present**: the script skips the whole fetch
  step with a warning; install one of them (`sudo apt install curl`) and
  re-run.
- **Corporate proxy / blocked GitHub raw content**: the font URLs point at
  `github.com/google/fonts/raw/...` (OFL sources from the `google/fonts`
  repo). If that host is blocked, download the fonts manually from
  [Google Fonts](https://fonts.google.com/specimen/DotGothic16) and
  [Zen Dots](https://fonts.google.com/specimen/Zen+Dots), then drop the
  `.ttf` files into `~/.local/share/fonts/lmdesktopplus/` and run
  `fc-cache -f`.

## Cinnamon theme notes

v1 does not ship a full custom Cinnamon/Metacity theme — see
[`packages/cinnamon/README.md`](../packages/cinnamon/README.md) for what is
and isn't themed today (wallpaper + GTK CSS + best-effort `Mint-Y-Dark` /
`Papirus-Dark` gsettings hints). If those theme/icon names aren't installed
on your system, `gsettings set` calls for them are best-effort (`|| true`)
and won't fail the install; pick any dark GTK/icon theme manually in
**System Settings → Themes**.

## General troubleshooting

- **Unsupported OS refusal**: `install.sh` refuses to run on anything that
  isn't Linux Mint or an Ubuntu/Debian-family `ID_LIKE`. Override with
  `--force` or `FORCE=1` if you know what you're doing.
- **Want to preview without changing anything?** `./install.sh --dry-run`
  logs every planned action (apt packages, symlinks, gsettings, bashrc
  append, session registration) without touching the system.
- **Rolling back**: run `./uninstall.sh` to restore backed-up files and
  strip the bashrc snippet. Backups under `~/.lmdesktopplus-backup/` are
  never deleted automatically, so nothing is lost even if you skip
  uninstalling.
