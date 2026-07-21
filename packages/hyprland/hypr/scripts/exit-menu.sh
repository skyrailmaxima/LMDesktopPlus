#!/usr/bin/env bash
# Confirm before leaving Hyprland (waybar button + Super+E).
set -euo pipefail

if ! command -v hyprctl >/dev/null 2>&1; then
  echo "hyprctl not found — not in a Hyprland session?" >&2
  exit 1
fi

if ! command -v rofi >/dev/null 2>&1; then
  # No menu tool — exit immediately (same as legacy Super+E).
  exec hyprctl dispatch exit
fi

choice="$(
  printf '%s\n' 'Exit Hyprland' 'Cancel' \
    | rofi -dmenu -i -p 'session' -mesg 'Leave Hyprland and return to the TTY / greeter'
)"

case "${choice:-}" in
  'Exit Hyprland') hyprctl dispatch exit ;;
  *) exit 0 ;;
esac
