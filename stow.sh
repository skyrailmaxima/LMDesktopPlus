#!/usr/bin/env bash
# Optional GNU stow frontend for LMDesktopPlus rice packages.
# Installer-driven install.sh remains the primary path; this is Task 23 stow mode.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
STOW_DIR="$REPO_ROOT/packaging/.stow-build"
# cloud-init / restricted shells may not export HOME — fall back for Target default.
: "${HOME:=${STOW_TARGET:-/tmp}}"
TARGET="${STOW_TARGET:-$HOME}"
DRY_RUN=0
DELETE=0
RESTOW=0
WITH_HYPR=0
MATERIALIZE_ONLY=0

usage() {
  cat <<'EOF'
Usage: ./stow.sh [--dry-run] [--restow] [--delete] [--with-hyprland] [--materialize-only] [--target DIR]

Materializes a GNU stow package tree from packages/{shared,hyprland} into
packaging/.stow-build/, then runs stow against TARGET (default: $HOME).

--materialize-only builds packaging/.stow-build/ without invoking stow
(useful in CI when GNU stow is not installed).

Falls back to printing install.sh link guidance when GNU stow is not installed
and --materialize-only was not requested. install.sh remains the primary path.
EOF
}

log() { printf 'stow: %s\n' "$*"; }
die() { printf 'stow: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --restow) RESTOW=1 ;;
    --delete) DELETE=1 ;;
    --with-hyprland) WITH_HYPR=1 ;;
    --materialize-only) MATERIALIZE_ONLY=1 ;;
    --target) TARGET="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown flag: $1" ;;
  esac
  shift
done

link_into() {
  # link_into <repo-relative-src> <path-under-package-root>
  local src="$REPO_ROOT/$1"
  local dest="$STOW_DIR/$2"
  [[ -e "$src" || -L "$src" ]] || die "missing source $1"
  mkdir -p "$(dirname "$dest")"
  ln -sfn "$src" "$dest"
}

materialize() {
  rm -rf "$STOW_DIR"
  mkdir -p "$STOW_DIR/shared" "$STOW_DIR/hyprland"

  # shared → ~/.config/...
  link_into packages/shared/kitty/kitty.conf shared/.config/kitty/kitty.conf
  link_into packages/shared/rofi/config.rasi shared/.config/rofi/config.rasi
  link_into packages/shared/rofi/themes/matrix.rasi shared/.config/rofi/themes/matrix.rasi
  link_into packages/shared/tmux/tmux.conf shared/.config/tmux/tmux.conf
  link_into packages/shared/starship/starship.toml shared/.config/starship.toml
  link_into packages/shared/gtk-3.0/gtk.css shared/.config/gtk-3.0/gtk.css
  link_into packages/shared/gtk-4.0/gtk.css shared/.config/gtk-4.0/gtk.css
  link_into palette/vapor-matrix.theme shared/.config/vapor-matrix.theme

  if [[ "$WITH_HYPR" == "1" ]]; then
    link_into packages/hyprland/hypr/hyprland.conf hyprland/.config/hypr/hyprland.conf
    link_into packages/hyprland/hypr/hyprpaper.conf hyprland/.config/hypr/hyprpaper.conf
    link_into packages/hyprland/hypr/scripts/exit-menu.sh hyprland/.config/hypr/scripts/exit-menu.sh
    link_into packages/hyprland/waybar/config.jsonc hyprland/.config/waybar/config.jsonc
    link_into packages/hyprland/waybar/style.css hyprland/.config/waybar/style.css
  fi
}

run_stow() {
  local pkgs=(shared)
  [[ "$WITH_HYPR" == "1" ]] && pkgs+=(hyprland)
  local args=(-v -d "$STOW_DIR" -t "$TARGET")
  [[ "$DRY_RUN" == "1" ]] && args+=(-n)
  [[ "$RESTOW" == "1" ]] && args+=(-R)
  [[ "$DELETE" == "1" ]] && args+=(-D)
  # shellcheck disable=SC2086
  stow "${args[@]}" "${pkgs[@]}"
}

materialize
log "materialized $STOW_DIR (hyprland=$WITH_HYPR)"

if [[ "$MATERIALIZE_ONLY" == "1" ]]; then
  log "materialize-only: skipping stow"
  exit 0
fi

if ! command -v stow >/dev/null 2>&1; then
  log "GNU stow not found on PATH."
  log "Install stow, or use the primary installer:"
  log "  ./install.sh                  # Cinnamon + shared links"
  log "  ./install.sh --with-hyprland  # plus Hyprland package links"
  exit 2
fi

log "target=$TARGET dry_run=$DRY_RUN restow=$RESTOW delete=$DELETE hyprland=$WITH_HYPR"
run_stow
log "done (see docs/suggests.md for optional apt Suggests; install.sh remains primary)."
