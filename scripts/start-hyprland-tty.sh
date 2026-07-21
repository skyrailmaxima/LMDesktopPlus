#!/usr/bin/env bash
# Launch LMDesktopPlus Hyprland from a text console (TTY).
# Use this when LightDM does not list Wayland sessions (common on Mint).
set -euo pipefail

if ! command -v Hyprland >/dev/null 2>&1 && ! command -v hyprland >/dev/null 2>&1; then
  echo "Hyprland is not installed or not on PATH." >&2
  echo "Run: ./install.sh --with-hyprland   (from the LMDesktopPlus repo)" >&2
  exit 1
fi

if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
  echo "Already inside a graphical session (DISPLAY/WAYLAND_DISPLAY set)." >&2
  echo "Switch to a TTY first: Ctrl+Alt+F3, log in, then run this script again." >&2
  exit 1
fi

export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-wayland}"
export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-Hyprland}"

if command -v Hyprland >/dev/null 2>&1; then
  exec Hyprland "$@"
fi
exec hyprland "$@"
