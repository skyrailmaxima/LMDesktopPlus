#!/usr/bin/env bash
# LMDesktopPlus one-shot: install vapor//matrix rice + Hyprland, then switch.
#
# Usage (from a clone of this repo):
#   ./switch.sh              # install --with-hyprland, then start / arm Hyprland
#   ./switch.sh --now        # skip install; start Hyprland (must be on a TTY)
#   ./switch.sh --install-only
#   ./switch.sh --dry-run
#
# From inside Cinnamon we cannot safely openvt+su into Hyprland (no logind seat).
# Instead we arm a one-shot: Ctrl+Alt+F3 → log in → Hyprland starts once via bashrc.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/lib/common.sh"

DRY_RUN=0
INSTALL_ONLY=0
NOW_ONLY=0
FORCE_ARGS=()
HYPR_INSTALL_ARGS=()
ONCE_FLAG="$HOME/.local/share/lmdesktopplus/start-hyprland-once"

usage() {
  cat <<'EOF'
Usage: switch.sh [--now] [--install-only] [--dry-run] [--force]
                 [--allow-community-ppa] [--hyprland-source=distro|ppa|existing]

  (default)       Run ./install.sh --with-hyprland, then start or arm Hyprland.
  --now           Skip install; start Hyprland (run this on a text TTY).
  --install-only  Install/theme only; do not start or arm Hyprland.
  --dry-run       Pass through to install; do not start a session.
  --force         Pass --force to install.sh (unsupported OS override).
  --allow-community-ppa
                  Pass through to install.sh (explicit community PPA opt-in).
  --hyprland-source=...
                  Pass through to install.sh (distro|ppa|existing).

From a TTY (no desktop): Hyprland starts immediately.
From Cinnamon/LightDM: arms a one-shot — press Ctrl+Alt+F3, log in, and
Hyprland starts once automatically. Return to Cinnamon later with Ctrl+Alt+F7
(typical) after exiting Hyprland (waybar EXIT / Super+E).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --now) NOW_ONLY=1 ;;
    --install-only) INSTALL_ONLY=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE_ARGS+=(--force) ;;
    --allow-community-ppa) HYPR_INSTALL_ARGS+=(--allow-community-ppa) ;;
    --hyprland-source=distro|--hyprland-source=ppa|--hyprland-source=existing)
      HYPR_INSTALL_ARGS+=("$1")
      ;;
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
  [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]
}

start_hyprland_here() {
  if ! hypr_bin >/dev/null; then
    log_err "Hyprland not on PATH after install. See docs/install-notes.md"
    return 1
  fi
  # Prefer the hardened TTY launcher (runtime dir checks + startup log).
  exec "$REPO_ROOT/scripts/start-hyprland-tty.sh"
}

arm_hyprland_oneshot() {
  # Reliable handoff from a live graphical session: user logs into a real VT
  # (pam/systemd seat), bashrc sees the flag and execs Hyprland once.
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[dry-run] would arm one-shot flag: $ONCE_FLAG"
    log_info "[dry-run] then instruct: Ctrl+Alt+F3 → log in → Hyprland starts once"
    return 0
  fi
  ensure_dir "$(dirname "$ONCE_FLAG")"
  : > "$ONCE_FLAG"
  log_info "Hyprland cannot be started safely from inside Cinnamon (needs a real TTY seat)."
  log_info "Armed one-shot start. Do this now:"
  log_info "  1) Press Ctrl+Alt+F3"
  log_info "  2) Log in as $USER"
  log_info "  3) Hyprland starts automatically once"
  log_info "Leave Hyprland with waybar EXIT or Super+E, then Ctrl+Alt+F7 for Cinnamon (typical)."
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
  if [[ ${#HYPR_INSTALL_ARGS[@]} -gt 0 ]]; then
    install_cmd+=("${HYPR_INSTALL_ARGS[@]}")
  fi
  "${install_cmd[@]}"
  hash -r 2>/dev/null || true
else
  log_info "--now: skipping install"
fi

if [[ "$INSTALL_ONLY" == "1" ]]; then
  log_info "--install-only: done. Start later with: $REPO_ROOT/switch.sh --now  (on a TTY)"
  exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log_info "[dry-run] would start Hyprland next"
  if on_tty_console; then
    log_info "[dry-run] mode: exec on this TTY"
  else
    arm_hyprland_oneshot
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

arm_hyprland_oneshot
