#!/usr/bin/env bash
# LMDesktopPlus uninstaller — restores files from the newest backup made by
# install.sh, strips the bashrc snippet, and removes the wayland session file.
# The backup tree itself (~/.lmdesktopplus-backup/*) is never deleted.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"

DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
CINNAMON_ONLY=0

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--dry-run] [--cinnamon-only] [--force]

  --dry-run        Print planned actions without changing the system.
  --cinnamon-only   Present for symmetry with install.sh; has no effect here
                    since restore targets are read from the backup itself.
  --force           Present for symmetry with install.sh; unused here.

Env: DRY_RUN=1, FORCE=1 are equivalent to the flags above.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --cinnamon-only) CINNAMON_ONLY=1 ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) log_err "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

maybe() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] $*"
    return 0
  fi
  "$@"
}

BACKUP_PARENT="$HOME/.lmdesktopplus-backup"

# Known paths that install.sh may have created/linked/replaced. Restoring
# walks this list and, for each, restores the newest backup copy if one
# exists; entries with no backup are removed if they are LMDesktopPlus-owned
# symlinks (see remove_owned_symlink), otherwise left untouched.
KNOWN_PATHS=(
  "$HOME/.config/kitty/kitty.conf"
  "$HOME/.config/rofi/config.rasi"
  "$HOME/.config/rofi/themes/matrix.rasi"
  "$HOME/.tmux.conf"
  "$HOME/.config/tmux/tmux.conf"
  "$HOME/.config/starship.toml"
  "$HOME/.config/gtk-3.0/gtk.css"
  "$HOME/.config/gtk-4.0/gtk.css"
  "$HOME/.config/vapor-matrix.theme"
  "$HOME/.config/hypr/hyprland.conf"
  "$HOME/.config/hypr/hyprpaper.conf"
  "$HOME/.config/waybar/config.jsonc"
  "$HOME/.config/waybar/style.css"
  "$HOME/.bashrc"
)

find_newest_backup() {
  if [[ ! -d "$BACKUP_PARENT" ]]; then
    return 1
  fi
  # shellcheck disable=SC2012
  ls -1dt "$BACKUP_PARENT"/*/ 2>/dev/null | head -1 | sed 's:/$::'
}

is_lmdesktopplus_symlink() {
  local path="$1"
  [[ -L "$path" ]] || return 1
  local target
  target="$(readlink "$path")"
  case "$target" in
    "$REPO_ROOT"/*) return 0 ;;
    "$HOME/.local/share/lmdesktopplus"/*) return 0 ;;
    *) return 1 ;;
  esac
}

remove_owned_symlink() {
  local path="$1"

  if ! is_lmdesktopplus_symlink "$path"; then
    return 0
  fi

  local target
  target="$(readlink "$path")"

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would remove LMDesktopPlus symlink $path -> $target"
    return 0
  fi

  rm -f "$path"
  log_info "Removed LMDesktopPlus symlink $path -> $target"
}

restore_from_backup() {
  local newest="$1" path="$2"
  local rel="${path#"$HOME"/}"
  local backed_up=""

  if [[ -n "$newest" ]]; then
    backed_up="$newest/$rel"
  fi

  if [[ -n "$backed_up" && ( -e "$backed_up" || -L "$backed_up" ) ]]; then
    if [[ "$DRY_RUN" == "1" ]]; then
      log_info "[dry-run] would restore $backed_up -> $path"
      return 0
    fi

    ensure_dir "$(dirname "$path")"
    rm -rf "$path"
    cp -a "$backed_up" "$path"
    log_info "Restored $path from backup"
    return 0
  fi

  # No backup for this path: it was likely created fresh by install.sh
  # (e.g. a symlink on a clean install with nothing to replace). Remove it
  # if — and only if — it's a symlink owned by LMDesktopPlus, so we don't
  # leave every shared/hypr/waybar link behind on a clean-install uninstall.
  # Unrelated user files/symlinks are left untouched.
  remove_owned_symlink "$path"
}

remove_wayland_session() {
  local dest="/usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop"
  if [[ ! -f "$dest" ]]; then
    return 0
  fi
  if ! grep -q "LMDesktopPlus" "$dest" 2>/dev/null; then
    log_warn "$dest exists but does not mention LMDesktopPlus; leaving it in place"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would sudo remove $dest"
    return 0
  fi
  if sudo rm -f "$dest"; then
    log_info "Removed LMDesktopPlus wayland session -> $dest"
  else
    log_warn "Could not remove $dest (sudo failed/unavailable)"
  fi
}

strip_bashrc_markers() {
  local bashrc="$HOME/.bashrc"
  local marker_begin="# LMDesktopPlus begin"
  local marker_end="# LMDesktopPlus end"

  if [[ ! -f "$bashrc" ]] || ! grep -qF "$marker_begin" "$bashrc" 2>/dev/null; then
    log_info "No LMDesktopPlus markers found in $bashrc; nothing to strip"
    return 0
  fi

  # Require exactly one begin and one end marker, in order, before rewriting.
  # Multiple markers (or begin-only / out-of-order pairs) are malformed; a
  # stateful awk strip would delete everything from any second begin through
  # EOF, removing unrelated user configuration after a valid block.
  local begin_count end_count begin_line end_line
  begin_count="$(grep -cF "$marker_begin" "$bashrc" 2>/dev/null || true)"
  end_count="$(grep -cF "$marker_end" "$bashrc" 2>/dev/null || true)"

  if [[ "$begin_count" -ne 1 || "$end_count" -ne 1 ]]; then
    log_warn "Found $begin_count begin and $end_count end LMDesktopPlus markers in $bashrc (expected exactly one each); leaving $bashrc untouched"
    return 0
  fi

  begin_line="$(grep -nF "$marker_begin" "$bashrc" | cut -d: -f1)"
  end_line="$(grep -nF "$marker_end" "$bashrc" | cut -d: -f1)"

  if [[ -z "$begin_line" || -z "$end_line" || "$end_line" -le "$begin_line" ]]; then
    log_warn "LMDesktopPlus markers in $bashrc are out of order; leaving $bashrc untouched"
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would strip $marker_begin...$marker_end block from $bashrc"
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  awk -v begin="$begin_line" -v end="$end_line" '
    NR >= begin && NR <= end { next }
    { print }
  ' "$bashrc" > "$tmp"
  mv "$tmp" "$bashrc"
  log_info "Stripped LMDesktopPlus markers from $bashrc"
}

log_info "Looking for the newest LMDesktopPlus backup under $BACKUP_PARENT"
NEWEST_BACKUP="$(find_newest_backup || true)"

if [[ -z "${NEWEST_BACKUP:-}" ]]; then
  log_warn "No backup directory found under $BACKUP_PARENT; skipping file restore."
  log_warn "(Files with nothing to restore from will be removed if they are LMDesktopPlus-owned symlinks.)"
else
  log_info "Restoring from $NEWEST_BACKUP"
fi

for path in "${KNOWN_PATHS[@]}"; do
  restore_from_backup "${NEWEST_BACKUP:-}" "$path"
done

log_info "Stripping bashrc markers"
strip_bashrc_markers

log_info "Removing LMDesktopPlus wayland session (if present)"
remove_wayland_session

log_info "LMDesktopPlus uninstall complete. Backup tree(s) under $BACKUP_PARENT were left in place."
if [[ "$DRY_RUN" == "1" ]]; then
  log_info "This was a dry run; no changes were made."
fi
exit 0
