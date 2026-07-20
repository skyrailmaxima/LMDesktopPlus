# LMDesktopPlus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `skyrailmaxima/LMDesktopPlus` repo: installer-driven vapor//matrix rice for Linux Mint with Cinnamon default + optional Hyprland session.

**Architecture:** Shared palette + package trees under `packages/{shared,cinnamon,hyprland}`; `install.sh` detects Mint, installs apt deps, backups configs, symlinks packages, applies Cinnamon gsettings, and best-effort registers Hyprland.

**Tech Stack:** Bash, Linux Mint (Cinnamon), kitty, rofi, tmux, starship, waybar/Hyprland (optional), GTK CSS, gsettings.

## Global Constraints

- Target OS: Linux Mint (Ubuntu/Debian family); warn and continue on related distros, refuse on unrelated with `--force` override only.
- Palette tokens must match spec: mag `#ff2e97`, pink `#ff71ce`, cyan `#01cdfe`, mint `#05ffa1`, purple `#b967ff`, grn `#00ff70`, grn2 `#8dffbe`, amber `#ffcc44`, bg `#05060a`, bg2 `#0b0817`.
- Kitty opacity: `0.90`.
- Backup root: `~/.lmdesktopplus-backup/<timestamp>/`.
- Bashrc changes: append only between `# LMDesktopPlus begin` / `# LMDesktopPlus end`.
- Hyprland: fail soft; Cinnamon path must still succeed.
- Do not commit secrets; do not force-push; do not amend unless user asks.
- Repo remote target: `https://github.com/skyrailmaxima/LMDesktopPlus`.
- Preview HTML may be moved to `assets/preview/`; `_extracted*` build artifacts must be gitignored.

---

## File structure (create during tasks)

```
install.sh
uninstall.sh
lib/common.sh
lib/detect.sh
lib/packages-apt.sh
palette/vapor-matrix.theme
packages/shared/kitty/kitty.conf
packages/shared/rofi/config.rasi
packages/shared/rofi/themes/matrix.rasi
packages/shared/tmux/tmux.conf
packages/shared/starship/starship.toml
packages/shared/bash/bashrc.snippet
packages/shared/gtk-3.0/gtk.css
packages/shared/gtk-4.0/gtk.css
packages/cinnamon/README.md
packages/hyprland/hypr/hyprland.conf
packages/hyprland/hypr/hyprpaper.conf
packages/hyprland/waybar/config.jsonc
packages/hyprland/waybar/style.css
packages/hyprland/sessions/lmdesktopplus-hyprland.desktop
scripts/apply-cinnamon-gsettings.sh
scripts/fetch-fonts.sh
assets/wallpapers/vapor-matrix.svg
assets/preview/NeonRice-Vaporwave-Matrix-Rice.html
tests/smoke-structure.sh
README.md
LICENSE
.gitignore
docs/install-notes.md
```

---

### Task 1: Repo skeleton, gitignore, palette, smoke test

**Files:**
- Create: `.gitignore`, `LICENSE`, `palette/vapor-matrix.theme`, `tests/smoke-structure.sh`, `README.md` (stub), `docs/install-notes.md` (stub)
- Move: `NeonRice - Vaporwave Matrix Rice.html` → `assets/preview/NeonRice-Vaporwave-Matrix-Rice.html`
- Delete or ignore: `_extracted/`, `_extracted_template.html`

**Interfaces:**
- Produces: `palette/vapor-matrix.theme` with `KEY=value` lines (`MAG=...` etc.) consumed by later package configs and installers

- [ ] **Step 1: Write failing smoke test**

Create `tests/smoke-structure.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
need() { [[ -e "$ROOT/$1" ]] || { echo "MISSING: $1"; fail=1; }; }
need "palette/vapor-matrix.theme"
need "install.sh"
need "uninstall.sh"
need "lib/common.sh"
need "packages/shared/kitty/kitty.conf"
need "packages/hyprland/hypr/hyprland.conf"
need "packages/cinnamon/README.md"
if [[ "$fail" -ne 0 ]]; then exit 1; fi
echo "structure OK"
```

- [ ] **Step 2: Run smoke test — expect FAIL**

Run: `bash tests/smoke-structure.sh`  
Expected: FAIL with several `MISSING:` lines

- [ ] **Step 3: Create palette + gitignore + move preview**

`palette/vapor-matrix.theme`:

```bash
# LMDesktopPlus vapor//matrix palette — source of truth
MAG=#ff2e97
PINK=#ff71ce
CYAN=#01cdfe
MINT=#05ffa1
PURPLE=#b967ff
GRN=#00ff70
GRN2=#8dffbe
AMBER=#ffcc44
BG=#05060a
BG2=#0b0817
KITTY_OPACITY=0.90
```

`.gitignore`:

```
_extracted/
_extracted_template.html
*.swp
.DS_Store
```

Move preview HTML into `assets/preview/`. Remove `_extracted*` from the working tree (do not commit them).

`LICENSE`: MIT with copyright holder `skyrailmaxima` and year `2026`.

Stub `README.md` title: `# LMDesktopPlus`.

- [ ] **Step 4: Re-run smoke — still FAIL on install/packages (expected)**

Run: `bash tests/smoke-structure.sh`  
Expected: palette present; other paths still MISSING

- [ ] **Step 5: Commit**

```bash
git init  # only if not already a repo
git add .gitignore LICENSE palette/vapor-matrix.theme tests/smoke-structure.sh README.md assets/preview docs/
git commit -m "$(cat <<'EOF'
chore: scaffold LMDesktopPlus palette, preview, and smoke test

EOF
)"
```

---

### Task 2: Shared lib helpers (`common.sh`, `detect.sh`)

**Files:**
- Create: `lib/common.sh`, `lib/detect.sh`
- Test: extend `tests/smoke-structure.sh` + add `tests/test-common.sh`

**Interfaces:**
- Produces:
  - `log_info`, `log_warn`, `log_err` → print to stderr with prefix
  - `backup_path SRC` → copies/moves collision into `$BACKUP_ROOT/...` preserving relative path under `$HOME`
  - `link_file SRC DEST` → backup DEST if exists and not already correct symlink; `ln -sfn`
  - `ensure_dir DIR`
  - `detect_os` → sets `OS_ID`, `OS_LIKE`, `IS_MINT` (`0|1`)
  - `require_mint_or_warn` → exit 1 if unsupported unless `FORCE=1`

- [ ] **Step 1: Write `tests/test-common.sh` (failing until lib exists)**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/common.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME"
export BACKUP_ROOT="$TMP/backup"
mkdir -p "$HOME/.config/kitty"
echo old > "$HOME/.config/kitty/kitty.conf"
mkdir -p "$TMP/pkg"
echo new > "$TMP/pkg/kitty.conf"
link_file "$TMP/pkg/kitty.conf" "$HOME/.config/kitty/kitty.conf"
[[ -L "$HOME/.config/kitty/kitty.conf" ]]
[[ -f "$BACKUP_ROOT"/*/.config/kitty/kitty.conf ]] || [[ -f $(find "$BACKUP_ROOT" -name kitty.conf | head -1) ]]
echo "common OK"
```

- [ ] **Step 2: Run test — expect FAIL (missing lib)**

Run: `bash tests/test-common.sh`  
Expected: FAIL cannot source `lib/common.sh`

- [ ] **Step 3: Implement `lib/common.sh` and `lib/detect.sh`**

`lib/common.sh` must define:

```bash
log_info() { printf '==> %s\n' "$*" >&2; }
log_warn() { printf '!!  %s\n' "$*" >&2; }
log_err()  { printf 'xx  %s\n' "$*" >&2; }

ensure_dir() { mkdir -p "$1"; }

# BACKUP_ROOT must be set by caller (timestamped).
backup_path() {
  local src="$1"
  [[ -e "$src" || -L "$src" ]] || return 0
  local rel="${src#"$HOME"/}"
  local dest="$BACKUP_ROOT/$rel"
  ensure_dir "$(dirname "$dest")"
  cp -a "$src" "$dest"
}

link_file() {
  local src="$1" dest="$2"
  ensure_dir "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    local cur
    cur=$(readlink "$dest")
    [[ "$cur" == "$src" ]] && return 0
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    backup_path "$dest"
    rm -rf "$dest"
  fi
  ln -sfn "$src" "$dest"
}
```

`lib/detect.sh`:

```bash
detect_os() {
  OS_ID=unknown
  OS_LIKE=
  IS_MINT=0
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_LIKE="${ID_LIKE:-}"
    [[ "$OS_ID" == "linuxmint" ]] && IS_MINT=1
  fi
}

require_mint_or_warn() {
  detect_os
  if [[ "$IS_MINT" -eq 1 ]]; then return 0; fi
  if [[ "${FORCE:-0}" == "1" ]]; then
    log_warn "Not Linux Mint ($OS_ID); continuing because FORCE=1"
    return 0
  fi
  if [[ "$OS_ID" =~ (ubuntu|debian) || "$OS_LIKE" =~ (ubuntu|debian) ]]; then
    log_warn "Not Mint ($OS_ID) but Debian-family; continuing"
    return 0
  fi
  log_err "Unsupported OS: $OS_ID. Re-run with FORCE=1 to override."
  return 1
}
```

- [ ] **Step 4: Run `tests/test-common.sh` — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add lib/common.sh lib/detect.sh tests/test-common.sh
git commit -m "$(cat <<'EOF'
feat: add install helper libs for backup and OS detect

EOF
)"
```

---

### Task 3: Apt package module

**Files:**
- Create: `lib/packages-apt.sh`

**Interfaces:**
- Consumes: `log_*` from `common.sh`
- Produces:
  - `APT_SHARED=(kitty rofi tmux btop curl wget git fonts-jetbrains-mono)`
  - `APT_HYPR_OPTIONAL=(waybar swaybg)` — install only if Hyprland path proceeds
  - `install_apt_packages()` — `sudo apt-get update` + `apt-get install -y` unless `DRY_RUN=1`

- [ ] **Step 1: Implement `lib/packages-apt.sh`**

```bash
APT_SHARED=(
  kitty rofi tmux btop curl wget git
  fonts-jetbrains-mono
)

APT_HYPR_OPTIONAL=(waybar swaybg)

install_apt_packages() {
  local extras=("$@")
  local pkgs=("${APT_SHARED[@]}" "${extras[@]}")
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log_info "DRY_RUN apt install: ${pkgs[*]}"
    return 0
  fi
  sudo apt-get update
  sudo apt-get install -y "${pkgs[@]}"
}
```

- [ ] **Step 2: Manual check**

Run: `DRY_RUN=1 bash -c 'source lib/common.sh; source lib/packages-apt.sh; install_apt_packages'`  
Expected: prints dry-run package list, exit 0

- [ ] **Step 3: Commit**

```bash
git add lib/packages-apt.sh
git commit -m "$(cat <<'EOF'
feat: add apt package lists for shared rice tools

EOF
)"
```

---

### Task 4: Shared app configs (kitty, rofi, tmux, starship, bash, gtk)

**Files:**
- Create all under `packages/shared/` listed in File structure

**Interfaces:**
- Consumes: palette hex values (hardcode matching tokens in each config; keep in sync with `palette/vapor-matrix.theme`)
- Produces: files ready for symlink into `~/.config/...` and bash snippet path

- [ ] **Step 1: Kitty**

`packages/shared/kitty/kitty.conf`:

```conf
# LMDesktopPlus vapor//matrix
font_family JetBrains Mono
font_size 12.0
background #05060a
foreground #8dffbe
cursor #05ffa1
selection_background #ff2e97
selection_foreground #ffffff
color0 #05060a
color1 #ff2e97
color2 #00ff70
color3 #ffcc44
color4 #01cdfe
color5 #b967ff
color6 #05ffa1
color7 #8dffbe
color8 #0b0817
color9 #ff71ce
color10 #00ff70
color11 #ffcc44
color12 #01cdfe
color13 #b967ff
color14 #05ffa1
color15 #ffffff
background_opacity 0.90
window_padding_width 8
```

- [ ] **Step 2: Rofi**

`packages/shared/rofi/config.rasi`:

```css
configuration {
  modi: "drun,run,window";
  show-icons: true;
  font: "JetBrains Mono 11";
}
@theme "themes/matrix"
```

`packages/shared/rofi/themes/matrix.rasi` — dark bg `#05060a`, selected `#ff2e97`, border `#01cdfe`, text `#8dffbe`.

- [ ] **Step 3: tmux + starship + bash snippet + gtk.css**

- `tmux.conf`: status style bg `#0b0817`, fg `#01cdfe`, active pane border `#ff2e97`
- `starship.toml`: format with cyan/magenta accents; character success `#00ff70`, error `#ff2e97`
- `bashrc.snippet`:

```bash
# LMDesktopPlus begin
export LMDESKTOPPLUS_DIR="${LMDESKTOPPLUS_DIR:-$HOME/.local/share/lmdesktopplus}"
if command -v starship >/dev/null 2>&1; then
  eval "$(starship init bash)"
fi
alias k='kitty'
alias rofi-apps='rofi -show drun'
# LMDesktopPlus end
```

- `gtk-3.0/gtk.css` and `gtk-4.0/gtk.css`: dark background, accent selection using mag/cyan

- [ ] **Step 4: Update smoke test expectations already covering kitty — run structure check partial**

Run: `test -f packages/shared/kitty/kitty.conf && echo OK`

- [ ] **Step 5: Commit**

```bash
git add packages/shared
git commit -m "$(cat <<'EOF'
feat: add shared kitty/rofi/tmux/starship/gtk vapor theme configs

EOF
)"
```

---

### Task 5: Wallpaper + font fetch script

**Files:**
- Create: `assets/wallpapers/vapor-matrix.svg`, `scripts/fetch-fonts.sh`

**Interfaces:**
- Produces: SVG wallpaper (sun + grid + dark bg) usable by Cinnamon and Hyprland
- `fetch-fonts.sh` installs DotGothic16 (and Zen Dots if fetchable) into `~/.local/share/fonts` and runs `fc-cache`

- [ ] **Step 1: Create SVG wallpaper** matching mockup (radial bg `#05060a`, cyan/magenta grid, gradient sun)

- [ ] **Step 2: `scripts/fetch-fonts.sh`** downloads Google Fonts zip or woff2 for DotGothic16 into `~/.local/share/fonts/lmdesktopplus/` (skip gracefully offline)

- [ ] **Step 3: Commit**

```bash
git add assets/wallpapers scripts/fetch-fonts.sh
git commit -m "$(cat <<'EOF'
feat: add vapor-matrix wallpaper and font fetch helper

EOF
)"
```

---

### Task 6: Cinnamon package + gsettings apply script

**Files:**
- Create: `packages/cinnamon/README.md`, `scripts/apply-cinnamon-gsettings.sh`

**Interfaces:**
- Produces: script that sets wallpaper to repo SVG (or copied path under `~/.local/share/lmdesktopplus/wallpapers/`), dark theme preferences where available, and documents manual Theme settings if a full Cinnamon theme ship is deferred
- v1 may use GTK CSS + wallpaper + icon hint rather than a full custom Cinnamon theme tarball if timeboxed — document clearly in README

- [ ] **Step 1: Implement `apply-cinnamon-gsettings.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
WALLPAPER="${1:?wallpaper path required}"
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "Would set wallpaper to $WALLPAPER"
  exit 0
fi
# Cinnamon background
gsettings set org.cinnamon.desktop.background picture-uri "file://$WALLPAPER"
gsettings set org.cinnamon.desktop.background picture-options "zoom"
# Prefer dark where supported
gsettings set org.cinnamon.desktop.interface gtk-theme "Mint-Y-Dark" || true
gsettings set org.cinnamon.desktop.interface icon-theme "Papirus-Dark" || true
```

- [ ] **Step 2: Write `packages/cinnamon/README.md`** describing hybrid intent and that full custom Cinnamon theme can land post-v1

- [ ] **Step 3: Commit**

```bash
git add packages/cinnamon scripts/apply-cinnamon-gsettings.sh
git commit -m "$(cat <<'EOF'
feat: add Cinnamon wallpaper/theme gsettings apply script

EOF
)"
```

---

### Task 7: Hyprland + waybar packages + session desktop

**Files:**
- Create: `packages/hyprland/hypr/hyprland.conf`, `packages/hyprland/hypr/hyprpaper.conf`, `packages/hyprland/waybar/config.jsonc`, `packages/hyprland/waybar/style.css`, `packages/hyprland/sessions/lmdesktopplus-hyprland.desktop`

**Interfaces:**
- Hyprland binds: Super+Return → kitty; Super+D → rofi; Super+E → exit
- Gaps: inner 6, outer 14 (from mockup)
- Border accent cyan/mag active
- waybar style uses palette colors
- Session `Exec=Hyprland` (or `hyprland` — detect during install)

- [ ] **Step 1: Write `hyprland.conf`** with monitor, exec-once waybar + hyprpaper/swaybg, decoration blur if available, general gaps 6/14, col.active_border cyan/mag

- [ ] **Step 2: waybar config + style** — modules: workspaces, clock, cpu, memory, network; colors from palette

- [ ] **Step 3: Session desktop file**

```desktop
[Desktop Entry]
Name=LMDesktopPlus Hyprland
Comment=Vapor//matrix Hyprland session (LMDesktopPlus)
Exec=Hyprland
Type=Application
DesktopNames=Hyprland
```

- [ ] **Step 4: Commit**

```bash
git add packages/hyprland
git commit -m "$(cat <<'EOF'
feat: add Hyprland, waybar, and login session desktop file

EOF
)"
```

---

### Task 8: `install.sh` and `uninstall.sh`

**Files:**
- Create: `install.sh`, `uninstall.sh`
- Modify: `tests/smoke-structure.sh` (should now PASS)

**Interfaces:**
- Consumes: all libs + package trees
- Flags: `--dry-run`, `--cinnamon-only`, `--force`
- Env: `FORCE=1`, `DRY_RUN=1`
- Install steps order: detect → apt → fonts → materialize share dir → link shared → link cinnamon assets → apply gsettings → try hypr → link hypr → install session desktop with sudo → append bashrc snippet → print done

- [ ] **Step 1: Implement `install.sh`**

Must:
1. Resolve `REPO_ROOT`
2. Parse flags
3. `source` libs
4. `require_mint_or_warn`
5. Set `BACKUP_ROOT=$HOME/.lmdesktopplus-backup/$(date +%Y%m%d-%H%M%S)`
6. `install_apt_packages` (+ optional hypr pkgs unless `--cinnamon-only`)
7. Copy/link wallpaper + palette into `~/.local/share/lmdesktopplus/`
8. `link_file` configs:
   - kitty → `~/.config/kitty/kitty.conf`
   - rofi → `~/.config/rofi/`
   - tmux → `~/.tmux.conf` or `~/.config/tmux/tmux.conf`
   - starship → `~/.config/starship.toml`
   - gtk css → `~/.config/gtk-3.0/gtk.css`, `gtk-4.0`
   - palette → `~/.config/vapor-matrix.theme`
9. Append bashrc snippet if markers absent
10. Run `apply-cinnamon-gsettings.sh`
11. Unless `--cinnamon-only`: if `command -v Hyprland || command -v hyprland`, link hypr/waybar and `sudo cp` session desktop to `/usr/share/wayland-sessions/`; else log skip with install-notes pointer
12. Exit 0

- [ ] **Step 2: Implement `uninstall.sh`**

Restore files from newest backup directory for known paths; remove wayland session file if it contains `LMDesktopPlus`; strip bashrc markers block; do not delete the backup tree.

- [ ] **Step 3: Run smoke structure — expect PASS**

Run: `bash tests/smoke-structure.sh`  
Expected: `structure OK`

- [ ] **Step 4: Dry-run install**

Run: `./install.sh --dry-run`  
Expected: logs planned actions, no apt changes, exit 0

- [ ] **Step 5: Commit**

```bash
git add install.sh uninstall.sh tests/smoke-structure.sh
git commit -m "$(cat <<'EOF'
feat: add install and uninstall entrypoints for Mint hybrid rice

EOF
)"
```

---

### Task 9: README + install notes + GitHub remote

**Files:**
- Modify: `README.md`, `docs/install-notes.md`

**Interfaces:**
- Documents clone URL, flags, session selection, Hyprland manual fallback

- [ ] **Step 1: Write README** covering hybrid model, quick start, flags, screenshots placeholder, license

- [ ] **Step 2: Write `docs/install-notes.md`** with Hyprland-on-Mint caveats and font troubleshooting

- [ ] **Step 3: Create GitHub repo and push** (requires user network auth)

```bash
gh repo create skyrailmaxima/LMDesktopPlus --public --source=. --remote=origin --push
```

If `gh` auth missing, stop and give the user the exact `gh auth login` + create commands.

- [ ] **Step 4: Final commit if README dirty**

```bash
git add README.md docs/install-notes.md
git commit -m "$(cat <<'EOF'
docs: add install guide for Cinnamon + optional Hyprland

EOF
)"
git push -u origin HEAD
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Hybrid Cinnamon + Hyprland | 6, 7, 8 |
| install.sh entrypoint + backups | 2, 8 |
| Shared palette | 1, 4 |
| kitty/rofi/tmux/starship/bash | 4 |
| Fail-soft Hyprland | 8 |
| Wallpaper + fonts | 5, 6 |
| GitHub skyrailmaxima/LMDesktopPlus | 9 |
| Dry-run / cinnamon-only | 8 |
| Uninstall restore | 8 |
| Non-goals excluded | — (no Pulsar/nix/stow/agents in tasks) |

## Placeholder scan

None intentional; Hyprland apt source is intentionally “best-effort + docs” per spec risk table.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-lmdesktopplus.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
