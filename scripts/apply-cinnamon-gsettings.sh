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
