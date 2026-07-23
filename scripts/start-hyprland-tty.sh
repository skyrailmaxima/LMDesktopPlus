#!/usr/bin/env bash
# Launch LMDesktopPlus Hyprland from a text console (TTY).
# Use this when LightDM does not list Wayland sessions (common on Mint).
set -euo pipefail

STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
LOG_DIR="$STATE_HOME/lmdesktopplus"
LOG_FILE="$LOG_DIR/hyprland-start.log"

log_line() {
  local msg="[$(date -Iseconds)] $*"
  mkdir -p "$LOG_DIR"
  printf '%s\n' "$msg" | tee -a "$LOG_FILE" >&2
}

if ! command -v Hyprland >/dev/null 2>&1 && ! command -v hyprland >/dev/null 2>&1; then
  log_line "ERROR: Hyprland is not installed or not on PATH."
  echo "Run: ./install.sh --with-hyprland   (distro packages only)" >&2
  echo "Or:  ./install.sh --with-hyprland --allow-community-ppa" >&2
  exit 1
fi

if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
  log_line "ERROR: Already inside a graphical session (DISPLAY/WAYLAND_DISPLAY set)."
  echo "Switch to a TTY first: Ctrl+Alt+F3, log in, then run this script again." >&2
  exit 1
fi

if [[ ! -t 0 ]]; then
  log_line "WARN: stdin is not a TTY; continuing, but a real console login is recommended."
fi

current_tty="$(tty 2>/dev/null || true)"
if [[ "$current_tty" != /dev/tty* ]]; then
  log_line "WARN: current tty is '${current_tty:-unknown}', expected /dev/tty*; continuing."
fi

if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  log_line "INFO: XDG_RUNTIME_DIR unset; using $XDG_RUNTIME_DIR"
fi
if [[ ! -d "$XDG_RUNTIME_DIR" ]]; then
  log_line "ERROR: XDG_RUNTIME_DIR '$XDG_RUNTIME_DIR' does not exist or is not a directory."
  exit 1
fi

# Minimal session identity for a TTY-started compositor. Keep app-compat
# variables (QT_QPA_PLATFORM, MOZ_ENABLE_WAYLAND, …) in Hyprland env config.
export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-wayland}"
export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-Hyprland}"
export XDG_SESSION_CLASS="${XDG_SESSION_CLASS:-user}"
export XDG_SESSION_DESKTOP="${XDG_SESSION_DESKTOP:-Hyprland}"

log_line "INFO: starting Hyprland from ${current_tty:-unknown} (runtime=$XDG_RUNTIME_DIR)"

if command -v Hyprland >/dev/null 2>&1; then
  exec Hyprland "$@"
fi
exec hyprland "$@"
