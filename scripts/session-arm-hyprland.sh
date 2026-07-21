#!/usr/bin/env bash
# Arm the existing bashrc one-shot handoff; never launch Hyprland from Cinnamon.
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ONCE_FLAG="$DATA_HOME/lmdesktopplus/start-hyprland-once"

mkdir -p "$(dirname "$ONCE_FLAG")"
: > "$ONCE_FLAG"

printf '%s\n' \
  "Hyprland one-shot armed." \
  "Press Ctrl+Alt+F3, log in, and Hyprland will start once automatically."
