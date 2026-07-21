#!/usr/bin/env bash
# LMDesktopPlus one-shot: install vapor//matrix rice + Hyprland, then switch.
#
# Usage (from a clone of this repo):
#   ./switch.sh              # install --with-hyprland, then start Hyprland
#   ./switch.sh --now        # skip install; just start Hyprland
#   ./switch.sh --install-only
#   ./switch.sh --dry-run
#
# Mint note: LightDM often hides Wayland sessions. This script starts Hyprland
# on a free TTY (via openvt when needed) so you do not depend on the greeter.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"

DRY_RUN=0
INSTALL_ONLY=0
NOW_ONLY=0
FORCE_ARGS=()

usage() {
  cat <<'EOF'
Usage: switch.sh [--now] [--install-only] [--dry-run] [--force]

  (default)       Run ./install.sh --with-hyprland, then switch to Hyprland.
  --now           Skip install; start Hyprland immediately (configs must exist).
  --install-only  Install/theme only; do not start Hyprland.
  --dry-run       Pass through to install; do not start a session.
  --force         Pass --force to install.sh (unsupported OS override).

After a successful switch you should be on Hyprland. Return to Cinnamon later
with Ctrl+Alt+F7 (or F1/F2) after exiting Hyprland, then pick Cinnamon at login.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --now) NOW_ONLY=1 ;;
    --install-only) INSTALL_ONLY=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE_ARGS+=(--force) ;;
    -h|--help) usage; exit 0 ;;
    *) log_err "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ "$NOW_ONLY" == "1" && "$INSTALL_ONLY" == "1" ]]; then
  log_err "Cannot combine --now with --install-only"
  exit 1
fi

hypr_bin() {
  if command -v Hyprland >/dev/null 2>&1; then
    printf '%s' Hyprland
  elif command -v hyprland >/dev/null 2>&1; then
    printf '%s' hyprland
  else
    return 1
  fi
}

on_tty_console() {
  # No graphical session attached — safe to exec Hyprland in-place.
  [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]
}

find_free_vt() {
  # Prefer VT 8–12 (away from LightDM/Cinnamon which is usually VT7).
  local n
  for n in 8 9 10 11 12; do
    if [[ ! -e "/sys/class/tty/tty${n}/active" ]] || \
       ! fgconsole 2>/dev/null | grep -qx "$n"; then
      # Heuristic: if /dev/ttyN exists, use it.
      if [[ -c "/dev/tty${n}" ]]; then
        printf '%s' "$n"
        return 0
      fi
    fi
  done
  printf '%s' 8
}

start_hyprland_here() {
  local bin
  bin="$(hypr_bin)" || {
    log_err "Hyprland not on PATH after install. See docs/install-notes.md"
    return 1
  }
  export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-wayland}"
  export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-Hyprland}"
  log_info "Starting $bin on this TTY…"
  exec "$bin"
}

start_hyprland_on_vt() {
  local bin vt
  bin="$(hypr_bin)" || {
    log_err "Hyprland not on PATH after install. See docs/install-notes.md"
    return 1
  }
  vt="$(find_free_vt)"
  log_info "Graphical session detected; launching $bin on VT${vt} via openvt…"
  log_info "Your current desktop stays on its VT — switch back with Ctrl+Alt+F7 (typical)."

  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would: sudo openvt -c $vt -f -s -- su - \"$USER\" -c '… $bin'"
    return 0
  fi

  if ! command -v openvt >/dev/null 2>&1; then
    log_warn "openvt not found (install package 'kbd'). Falling back to manual TTY steps:"
    log_warn "  1) Ctrl+Alt+F3 → log in"
    log_warn "  2) $REPO_ROOT/scripts/start-hyprland-tty.sh"
    return 1
  fi

  # Run as the same user on a fresh VT with a login-like environment.
  sudo openvt -c "$vt" -f -s -- \
    su - "$USER" -c "cd $(printf '%q' "$REPO_ROOT") && export XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=Hyprland && exec $(printf '%q' "$bin")"
}

### install ###################################################################
if [[ "$NOW_ONLY" != "1" ]]; then
  log_info "Installing LMDesktopPlus + Hyprland…"
  install_cmd=("$REPO_ROOT/install.sh" --with-hyprland)
  if [[ "$DRY_RUN" == "1" ]]; then
    install_cmd+=(--dry-run)
  fi
  if [[ ${#FORCE_ARGS[@]} -gt 0 ]]; then
    install_cmd+=("${FORCE_ARGS[@]}")
  fi
  "${install_cmd[@]}"
  hash -r 2>/dev/null || true
else
  log_info "--now: skipping install"
fi

if [[ "$INSTALL_ONLY" == "1" ]]; then
  log_info "--install-only: done. Start later with: $REPO_ROOT/switch.sh --now"
  exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log_info "[dry-run] would start Hyprland next (TTY or openvt)"
  if on_tty_console; then
    log_info "[dry-run] mode: exec on this TTY"
  else
    start_hyprland_on_vt || true
  fi
  log_info "Dry run complete."
  exit 0
fi

### switch ####################################################################
if ! hypr_bin >/dev/null; then
  log_err "Hyprland still missing after install. Fix packages, then: ./switch.sh --now"
  log_err "Manual Mint path: docs/install-notes.md"
  exit 1
fi

if on_tty_console; then
  start_hyprland_here
fi

start_hyprland_on_vt
