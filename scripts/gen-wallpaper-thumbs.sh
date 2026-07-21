#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/assets/wallpapers/vapor-matrix.svg"
THUMBS="$ROOT/assets/wallpapers/thumbs"
OUTPUT="$THUMBS/vapor-matrix.png"
PLACEHOLDER="$THUMBS/placeholder.png"

mkdir -p "$THUMBS"

if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert --width 320 --height 180 --keep-aspect-ratio \
    --output "$OUTPUT" "$SOURCE"
elif command -v convert >/dev/null 2>&1; then
  convert -background '#05060a' "$SOURCE" -thumbnail '320x180^' \
    -gravity center -extent 320x180 "$OUTPUT"
else
  echo "Install librsvg2-bin or ImageMagick to generate wallpaper thumbs." >&2
  exit 1
fi

if command -v convert >/dev/null 2>&1; then
  convert -size 320x180 xc:'#090713' \
    -fill '#160d2a' -draw 'rectangle 0,112 320,180' \
    -stroke '#01cdfe' -strokewidth 2 -fill none \
    -draw 'rectangle 10,10 309,169' \
    -stroke '#ff2e97' -draw 'line 0,112 320,112' \
    "$PLACEHOLDER"
else
  cp "$OUTPUT" "$PLACEHOLDER"
fi

echo "Generated $OUTPUT and $PLACEHOLDER"
