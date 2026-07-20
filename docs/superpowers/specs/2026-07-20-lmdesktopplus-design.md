# LMDesktopPlus Design Spec

**Date:** 2026-07-20  
**Repo:** `skyrailmaxima/LMDesktopPlus`  
**Status:** Approved (design + plan structure + build)  
**Source mockup:** `NeonRice - Vaporwave Matrix Rice.html` (vapor//matrix)

## 1. Problem

Personal Linux Mint deployments need a repeatable way to install a vaporwave/matrix desktop look and the tooling shown in the NeonRice HTML mockup. Stock Mint is Cinnamon; the mockup assumes Hyprland. The product must support both without forcing a single session.

## 2. Goals

- One-command install after clone: `./install.sh`
- **Cinnamon** remains the default session and is themed to the vapor//matrix palette
- Optional **Hyprland** session available at the display manager login screen
- Shared theme tokens so kitty, rofi, starship, tmux, Cinnamon/GTK, and Hyprland/waybar stay visually consistent
- Safe for personal machines: back up existing configs before writing
- Publishable as a personal GitHub repo for reuse across Mint installs

## 3. Non-goals (v1)

- Pulsar editor theming
- Agent sandbox directories (`~/agents/*`)
- Nix flake / pinned toolchain
- Live matrix-rain wallpaper (static wallpaper only in v1)
- GNU stow as the primary installer (optional later)
- Supporting non-Mint / non-Debian derivatives in v1
- Force-pushing or mutating remote git config as part of install

## 4. Architecture

### 4.1 Hybrid sessions

| Session | Role | UI surface |
|---------|------|------------|
| Cinnamon (default) | Daily Mint desktop | GTK + Cinnamon theme, themed panel, shared apps |
| Hyprland (optional) | Mockup-faithful rice | hyprland.conf, waybar, rofi, kitty |

Both sessions consume the same `palette/vapor-matrix.theme` and shared package configs under `packages/shared/`.

### 4.2 Installer-driven layout (Approach B)

`install.sh` is the single entrypoint. It:

1. Detects Linux Mint (or Ubuntu/Debian family) and warns otherwise
2. Installs apt packages for shared tools
3. Attempts Hyprland install via a documented Mint-compatible path; **fails soft** if unavailable (Cinnamon path still completes)
4. Backs up colliding paths to `~/.lmdesktopplus-backup/<timestamp>/`
5. Symlinks (preferred) or copies package trees into `$HOME`
6. Installs fonts and wallpaper
7. Registers a Hyprland `.desktop` session when Hyprland binaries exist
8. Prints post-install instructions (logout → choose session)

`uninstall.sh` restores from the latest backup where possible and removes session desktop files installed by this repo.

### 4.3 Shared palette

Canonical file: `palette/vapor-matrix.theme`

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

Fonts (install via packages or download): JetBrains Mono, DotGothic16, Zen Dots (display; fallback to a packaged geometric sans if Zen Dots fetch fails).

### 4.4 Repository layout

```
LMDesktopPlus/
  README.md
  LICENSE
  .gitignore
  install.sh
  uninstall.sh
  lib/
    common.sh              # logging, backup, link helpers
    detect.sh              # OS / session detection
    packages-apt.sh        # apt package lists + install
  palette/
    vapor-matrix.theme     # KEY=value tokens
  packages/
    shared/
      kitty/
      rofi/
      tmux/
      starship/
      bash/
      fonts/               # optional local font files or fetch script
      wallpaper/
      gtk-3.0/             # gtk.css overrides
      gtk-4.0/
    cinnamon/
      themes/              # Cinnamon + Metacity-ish naming as needed
      cinnamon-settings.md # documented gsettings keys applied by install
    hyprland/
      hypr/
      waybar/
      sessions/            # hyprland.desktop for /usr/share/wayland-sessions
  assets/
    preview/               # keep or reference NeonRice HTML
    wallpapers/
  scripts/
    apply-cinnamon-gsettings.sh
    generate-from-palette.sh  # optional: expand theme into app configs
  docs/
    superpowers/specs/
    superpowers/plans/
    install-notes.md
  tests/
    smoke-install.sh       # dry-run / structure checks (no root required)
```

### 4.5 Package mapping (mockup → v1)

| Mockup | v1 target |
|--------|-----------|
| `~/.config/vapor-matrix.theme` | Symlink from `palette/vapor-matrix.theme` |
| kitty opacity 0.90 | `packages/shared/kitty/` |
| rofi `matrix.rasi` | `packages/shared/rofi/` |
| tmux.conf | `packages/shared/tmux/` |
| starship.toml | `packages/shared/starship/` |
| bash + aliases | `packages/shared/bash/` (append block, do not clobber entire `.bashrc`) |
| hyprland.conf | `packages/hyprland/hypr/` |
| waybar | `packages/hyprland/waybar/` |
| Cinnamon look | `packages/cinnamon/` + gsettings script |
| wallpaper | `assets/wallpapers/` + set for Cinnamon; Hyprland `hyprpaper` or `swaybg` |

### 4.6 Apt packages (v1)

**Shared / Cinnamon path:** `kitty`, `rofi`, `tmux`, `btop`, `curl`, `wget`, `git`, `fonts-jetbrains-mono`, `papirus-icon-theme` (optional), `feh` or Cinnamon wallpaper via gsettings.

**Hyprland path (best-effort):** Document current Mint-viable source (e.g. official Hyprland install guidance for Ubuntu/Debian derivatives). Install `waybar`, `hyprpaper` or `swaybg`, `xdg-desktop-portal-hyprland` when available. If Hyprland cannot be installed, log a clear skip and finish Cinnamon successfully.

### 4.7 Safety

- Never run destructive git commands as part of install
- Backup before overwrite; refuse to delete backups automatically
- `install.sh --dry-run` prints actions without changing the system
- `install.sh --cinnamon-only` skips Hyprland attempts
- Do not write secrets; no `.env` with credentials in repo

### 4.8 GitHub

- Remote: `https://github.com/skyrailmaxima/LMDesktopPlus`
- Public or private at owner discretion
- README documents clone + `./install.sh` and session selection
- NeonRice HTML may live under `assets/preview/` as design reference (large file; prefer Git LFS or link if size is painful)

## 5. User-facing success criteria

On a fresh Linux Mint machine with network:

1. `git clone https://github.com/skyrailmaxima/LMDesktopPlus.git && cd LMDesktopPlus && ./install.sh`
2. After logout/login, **Cinnamon** shows vapor//matrix colors, wallpaper, kitty/rofi/starship themed
3. If Hyprland installed, login greeter lists **Hyprland**; that session shows waybar + matching palette
4. Re-running `./install.sh` is idempotent (re-links, refreshes backup only when replacing files)
5. `./uninstall.sh` can restore prior configs from backup

## 6. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hyprland hard to install on Mint | Fail soft; Cinnamon-only still succeeds; document manual Hyprland steps |
| Zen Dots / DotGothic16 not in apt | Fetch from Google Fonts or ship woff/ttf under `packages/shared/fonts/` |
| Clobbering user `.bashrc` | Append marked block between `# LMDesktopPlus begin/end` |
| Large preview HTML in git | Optional; exclude from default clone docs if needed |

## 7. Future (post-v1)

- Stow mode (`./stow.sh`)
- Pulsar theme package
- Live matrix wallpaper (GLSL/wallpaper engine or HTML wallpaper)
- Agent workspace helpers from mockup
- Nix flake for pinned toolchain

## 8. Approval

- Hybrid sessions: approved
- Installer-driven (not stow-first): approved
- Repo name / owner: `skyrailmaxima/LMDesktopPlus`: approved
- Design conversation approval: 2026-07-20
