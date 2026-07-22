#!/usr/bin/env bash
# LMDesktopPlus installer — Linux Mint Cinnamon + optional Hyprland hybrid rice.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/detect.sh"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/packages-apt.sh"

DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
CINNAMON_ONLY=0
WITH_HYPRLAND=0
ALLOW_COMMUNITY_PPA=0
HYPRLAND_SOURCE=""

usage() {
  cat <<'EOF'
Usage: install.sh [--dry-run] [--cinnamon-only] [--with-hyprland]
                  [--allow-community-ppa] [--hyprland-source=distro|ppa|existing]
                  [--force]

  --dry-run                 Print planned actions without changing the system.
  --cinnamon-only           Skip Hyprland/waybar setup, even if Hyprland is installed.
  --with-hyprland           Best-effort install Hyprland from distro packages only,
                            then link configs / session when available.
  --allow-community-ppa     With --with-hyprland: if distro packages fail, allow
                            adding ppa:cppiber/hyprland (explicit opt-in).
  --hyprland-source=distro  Only try distro/universe packages (default with --with-hyprland).
  --hyprland-source=ppa     Allow community PPA (implies --allow-community-ppa).
  --hyprland-source=existing
                            Require Hyprland already on PATH; do not install packages.
  --force                   Continue on unsupported OS (same as FORCE=1).

Env: DRY_RUN=1, FORCE=1 are equivalent to the flags above.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --cinnamon-only) CINNAMON_ONLY=1 ;;
    --with-hyprland) WITH_HYPRLAND=1 ;;
    --allow-community-ppa) ALLOW_COMMUNITY_PPA=1 ;;
    --hyprland-source=distro) HYPRLAND_SOURCE=distro ;;
    --hyprland-source=ppa) HYPRLAND_SOURCE=ppa; ALLOW_COMMUNITY_PPA=1 ;;
    --hyprland-source=existing) HYPRLAND_SOURCE=existing ;;
    --hyprland-source=*)
      log_err "Unknown hyprland source: ${1#*=} (use distro|ppa|existing)"
      usage
      exit 1
      ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) log_err "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ "$CINNAMON_ONLY" == "1" && "$WITH_HYPRLAND" == "1" ]]; then
  log_err "Cannot combine --cinnamon-only with --with-hyprland"
  exit 1
fi
if [[ -n "$HYPRLAND_SOURCE" && "$WITH_HYPRLAND" != "1" ]]; then
  log_err "--hyprland-source requires --with-hyprland"
  exit 1
fi
if [[ "$ALLOW_COMMUNITY_PPA" == "1" && "$WITH_HYPRLAND" != "1" ]]; then
  log_err "--allow-community-ppa requires --with-hyprland"
  exit 1
fi

export DRY_RUN FORCE

# Runs "$@" unless DRY_RUN=1, in which case it just logs the intent.
maybe() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] $*"
    return 0
  fi
  "$@"
}

require_mint_or_warn || exit 1

BACKUP_ROOT="$HOME/.lmdesktopplus-backup/$(date +%Y%m%d-%H%M%S)"
export BACKUP_ROOT
log_info "Backups (if any existing files are replaced) go to $BACKUP_ROOT"

SHARE_DIR="$HOME/.local/share/lmdesktopplus"
WALLPAPER_SRC_SVG="$REPO_ROOT/assets/wallpapers/vapor-matrix.svg"
WALLPAPER_DEST_SVG="$SHARE_DIR/wallpapers/vapor-matrix.svg"
WALLPAPER_DEST_PNG="$SHARE_DIR/wallpapers/vapor-matrix.png"
PALETTE_SRC="$REPO_ROOT/palette/vapor-matrix.theme"
PALETTE_DEST="$SHARE_DIR/palette/vapor-matrix.theme"

detect_hyprland() {
  HYPR_AVAILABLE=0
  HYPR_BIN=""
  if command -v Hyprland >/dev/null 2>&1; then
    HYPR_AVAILABLE=1
    HYPR_BIN="Hyprland"
  elif command -v hyprland >/dev/null 2>&1; then
    HYPR_AVAILABLE=1
    HYPR_BIN="hyprland"
  fi
}

detect_hyprland

### 0. optional Hyprland package install #####################################
if [[ "$WITH_HYPRLAND" == "1" ]]; then
  log_info "--with-hyprland: installing compositor (source=${HYPRLAND_SOURCE:-distro})"
  hypr_install_args=()
  if [[ "$ALLOW_COMMUNITY_PPA" == "1" ]]; then
    hypr_install_args+=(--allow-community-ppa)
  fi
  if [[ -n "$HYPRLAND_SOURCE" ]]; then
    hypr_install_args+=(--hyprland-source="$HYPRLAND_SOURCE")
  fi
  if DRY_RUN="$DRY_RUN" bash "$REPO_ROOT/scripts/install-hyprland-mint.sh" "${hypr_install_args[@]}"; then
    hash -r 2>/dev/null || true
    detect_hyprland
    if [[ "$DRY_RUN" == "1" && "$HYPR_AVAILABLE" != "1" ]]; then
      HYPR_AVAILABLE=1
      HYPR_BIN="Hyprland"
      log_info "[dry-run] assuming Hyprland will be on PATH after package install"
    fi
  else
    log_warn "Hyprland package install failed; continuing with Cinnamon path"
  fi
fi

### 1. apt packages ##########################################################
log_info "Installing apt packages"
if [[ "$CINNAMON_ONLY" == "1" ]]; then
  install_apt_packages
else
  install_apt_packages "${APT_HYPR_OPTIONAL[@]}"
fi

### 2. fonts ##################################################################
log_info "Fetching display fonts"
bash "$REPO_ROOT/scripts/fetch-fonts.sh" || log_warn "Font fetch script exited non-zero; continuing"

### 3. materialize ~/.local/share/lmdesktopplus ##############################
materialize_wallpaper() {
  maybe ensure_dir "$SHARE_DIR/wallpapers"
  maybe ensure_dir "$SHARE_DIR/palette"

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would copy $WALLPAPER_SRC_SVG -> $WALLPAPER_DEST_SVG"
    log_info "[dry-run] would rasterize SVG -> $WALLPAPER_DEST_PNG (convert/rsvg-convert/inkscape) or fall back to swaybg+SVG"
    log_info "[dry-run] would copy $PALETTE_SRC -> $PALETTE_DEST"
    return 0
  fi

  cp -a "$WALLPAPER_SRC_SVG" "$WALLPAPER_DEST_SVG"
  cp -a "$PALETTE_SRC" "$PALETTE_DEST"

  # Try each available rasterizer in turn; a converter being present is no
  # guarantee it will succeed (e.g. a broken ImageMagick policy.xml), so a
  # failed attempt falls through to the next converter instead of silently
  # leaving no PNG behind.
  local rasterized=0

  if [[ "$rasterized" == "0" ]] && command -v convert >/dev/null 2>&1; then
    if convert -background none "$WALLPAPER_SRC_SVG" "$WALLPAPER_DEST_PNG"; then
      log_info "Rasterized wallpaper -> $WALLPAPER_DEST_PNG (imagemagick)"
      rasterized=1
    else
      log_warn "convert (imagemagick) failed to rasterize the wallpaper; trying next converter"
    fi
  fi

  if [[ "$rasterized" == "0" ]] && command -v rsvg-convert >/dev/null 2>&1; then
    if rsvg-convert -o "$WALLPAPER_DEST_PNG" "$WALLPAPER_SRC_SVG"; then
      log_info "Rasterized wallpaper -> $WALLPAPER_DEST_PNG (rsvg-convert)"
      rasterized=1
    else
      log_warn "rsvg-convert failed to rasterize the wallpaper; trying next converter"
    fi
  fi

  if [[ "$rasterized" == "0" ]] && command -v inkscape >/dev/null 2>&1; then
    if inkscape "$WALLPAPER_SRC_SVG" --export-type=png --export-filename="$WALLPAPER_DEST_PNG" >/dev/null 2>&1; then
      log_info "Rasterized wallpaper -> $WALLPAPER_DEST_PNG (inkscape)"
      rasterized=1
    else
      log_warn "inkscape failed to rasterize the wallpaper"
    fi
  fi

  if [[ "$rasterized" == "0" ]]; then
    rm -f "$WALLPAPER_DEST_PNG" 2>/dev/null || true
    log_warn "No SVG rasterizer produced a PNG (convert/rsvg-convert/inkscape missing or all failed)."
    log_warn "hyprpaper.conf expects a PNG at $WALLPAPER_DEST_PNG; it will not find one."
    log_warn "Falling back: use swaybg with the SVG directly. In packages/hyprland/hypr/hyprland.conf,"
    log_warn "comment out 'exec-once = hyprpaper' and uncomment the 'exec-once = swaybg ...' line."
    log_warn "See docs/install-notes.md for details."
  fi
}
log_info "Materializing wallpaper + palette under $SHARE_DIR"
materialize_wallpaper

### 4. link shared configs ####################################################
link_shared_configs() {
  maybe link_file "$REPO_ROOT/packages/shared/kitty/kitty.conf" "$HOME/.config/kitty/kitty.conf"
  maybe link_file "$REPO_ROOT/packages/shared/rofi/config.rasi" "$HOME/.config/rofi/config.rasi"
  maybe link_file "$REPO_ROOT/packages/shared/rofi/themes/matrix.rasi" "$HOME/.config/rofi/themes/matrix.rasi"

  local tmux_dest="$HOME/.tmux.conf"
  if [[ -d "$HOME/.config/tmux" ]]; then
    tmux_dest="$HOME/.config/tmux/tmux.conf"
  elif command -v tmux >/dev/null 2>&1; then
    local tmux_ver smallest
    tmux_ver="$(tmux -V 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)"
    if [[ -n "$tmux_ver" ]]; then
      # tmux >= 3.1 supports the XDG path ~/.config/tmux/tmux.conf.
      smallest="$(printf '%s\n%s\n' "$tmux_ver" "3.1" | sort -V | head -1)"
      [[ "$smallest" == "3.1" ]] && tmux_dest="$HOME/.config/tmux/tmux.conf"
    fi
  fi
  maybe link_file "$REPO_ROOT/packages/shared/tmux/tmux.conf" "$tmux_dest"

  maybe link_file "$REPO_ROOT/packages/shared/starship/starship.toml" "$HOME/.config/starship.toml"
  maybe link_file "$REPO_ROOT/packages/shared/gtk-3.0/gtk.css" "$HOME/.config/gtk-3.0/gtk.css"
  maybe link_file "$REPO_ROOT/packages/shared/gtk-4.0/gtk.css" "$HOME/.config/gtk-4.0/gtk.css"
  maybe link_file "$PALETTE_SRC" "$HOME/.config/vapor-matrix.theme"
}
log_info "Linking shared configs (kitty, rofi, tmux, starship, gtk, palette)"
link_shared_configs

### 5. cinnamon assets ########################################################
# v1 packages/cinnamon ships docs only (no theme tarball yet, see packages/cinnamon/README.md);
# the wallpaper + gtk-theme/icon-theme hints are applied via gsettings below.
log_info "Cinnamon package is docs-only in v1; nothing extra to link"

### 6. apply cinnamon gsettings ###############################################
# Cinnamon/GTK can render SVG backgrounds; prefer the rasterized PNG when it
# exists (matches what hyprpaper needs), else fall back to the SVG copy.
GSETTINGS_WALLPAPER="$WALLPAPER_DEST_PNG"
if [[ "$DRY_RUN" != "1" && ! -f "$WALLPAPER_DEST_PNG" ]]; then
  GSETTINGS_WALLPAPER="$WALLPAPER_DEST_SVG"
fi
log_info "Applying Cinnamon gsettings (wallpaper, gtk-theme, icon-theme)"
bash "$REPO_ROOT/scripts/apply-cinnamon-gsettings.sh" "$GSETTINGS_WALLPAPER" || log_warn "gsettings apply script exited non-zero; continuing"

### 7. Hyprland (optional) ####################################################
link_hypr_assets() {
  maybe link_file "$REPO_ROOT/packages/hyprland/hypr/hyprland.conf" "$HOME/.config/hypr/hyprland.conf"
  maybe link_file "$REPO_ROOT/packages/hyprland/hypr/hyprpaper.conf" "$HOME/.config/hypr/hyprpaper.conf"
  maybe link_file "$REPO_ROOT/packages/hyprland/hypr/scripts/exit-menu.sh" "$HOME/.config/hypr/scripts/exit-menu.sh"
  maybe link_file "$REPO_ROOT/packages/hyprland/waybar/config.jsonc" "$HOME/.config/waybar/config.jsonc"
  maybe link_file "$REPO_ROOT/packages/hyprland/waybar/style.css" "$HOME/.config/waybar/style.css"
}

install_session_desktop() {
  local dest="/usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop"
  # Substitute the detected binary name (Hyprland vs hyprland) into Exec=/
  # TryExec= so the installed session always launches the binary that's
  # actually on PATH, even if it differs from the template default.
  local bin="${HYPR_BIN:-Hyprland}"
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would sudo install wayland session -> $dest (Exec=$bin, TryExec=$bin)"
    return 0
  fi
  local tmp_desktop
  tmp_desktop="$(mktemp)"
  sed -e "s/^TryExec=.*/TryExec=$bin/" \
      -e "s/^Exec=.*/Exec=$bin/" \
      "$REPO_ROOT/packages/hyprland/sessions/lmdesktopplus-hyprland.desktop" > "$tmp_desktop"
  if sudo cp "$tmp_desktop" "$dest"; then
    log_info "Installed Hyprland wayland session -> $dest (Exec=$bin, TryExec=$bin)"
  else
    log_warn "Could not install wayland session file (sudo failed/unavailable); see docs/install-notes.md"
  fi
  rm -f "$tmp_desktop"
}

if [[ "$CINNAMON_ONLY" == "1" ]]; then
  log_info "--cinnamon-only: skipping Hyprland/waybar setup"
elif [[ "$HYPR_AVAILABLE" == "1" ]]; then
  log_info "Hyprland detected; linking hypr/waybar configs and registering wayland session"
  link_hypr_assets
  install_session_desktop
else
  log_warn "Hyprland not found on PATH; skipping Hyprland/waybar setup."
  log_warn "Install with: ./install.sh --with-hyprland"
  log_warn "Community PPA (opt-in): ./install.sh --with-hyprland --allow-community-ppa"
  log_warn "Or see docs/install-notes.md / scripts/start-hyprland-tty.sh for the Mint TTY path."
fi

### 8. bashrc snippet ##########################################################
append_bashrc_snippet() {
  local bashrc="$HOME/.bashrc"
  local marker="# LMDesktopPlus begin"

  if [[ -f "$bashrc" ]] && grep -qF "$marker" "$bashrc" 2>/dev/null; then
    log_info "bashrc already has LMDesktopPlus markers; skipping append"
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would append packages/shared/bash/bashrc.snippet to $bashrc"
    return 0
  fi

  backup_path "$bashrc"
  {
    echo ""
    cat "$REPO_ROOT/packages/shared/bash/bashrc.snippet"
  } >> "$bashrc"
  log_info "Appended LMDesktopPlus snippet to $bashrc"
}
log_info "Updating ~/.bashrc"
append_bashrc_snippet

log_info "LMDesktopPlus install complete."
if [[ "$DRY_RUN" == "1" ]]; then
  log_info "This was a dry run; no changes were made."
fi
exit 0
