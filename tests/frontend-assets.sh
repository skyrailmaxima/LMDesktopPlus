#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC="$ROOT/src/lmdesktopplus/static"

grep -q -- '--dv-accent' "$STATIC/digitalvapor.css"
grep -q 'Digitalvapor' "$STATIC/digitalvapor.js"
grep -q 'digitalvapor.css' "$STATIC/index.html"
grep -q 'digitalvapor.js' "$STATIC/index.html"
grep -q 'data-bind="adapters.audio.volume"' "$STATIC/index.html"
grep -q 'data-audio-volume' "$STATIC/app.js"
grep -q '"/api/v1/adapter/audio"' "$STATIC/app.js"
grep -q '}, 100);' "$STATIC/app.js"
grep -q 'previousVolume' "$STATIC/app.js"
grep -q 'currentAudio.volume = previousVolume' "$STATIC/app.js"
if grep -Eq '<script[^>]*>[^<]*window\.LMDP_TOKEN' "$STATIC/index.html"; then
  echo "inline token script remains in index.html" >&2
  exit 1
fi
if find "$ROOT" -type f \( -iname '*.woff' -o -iname '*.woff2' -o -iname '*.ttf' -o -iname '*.otf' \) -print -quit | grep -q .; then
  echo "font binary leaked into source tree" >&2
  exit 1
fi
ICONS="$STATIC/icons"
test -f "$ICONS/manifest.json"
python3 - "$ICONS" <<'PY'
import json
import sys
from pathlib import Path

icons = Path(sys.argv[1])
manifest = json.loads((icons / "manifest.json").read_text(encoding="utf-8"))
expected = {
    "audio.volume", "audio.mute", "display.brightness", "bluetooth", "notify", "update",
    "session.hyprland", "session.cinnamon", "wallpaper", "clipboard", "camera", "vpn", "usb", "power",
}
if set(manifest) != expected:
    raise SystemExit(f"manifest keys mismatch: {set(manifest) ^ expected}")
for icon_id, entry in manifest.items():
    svg = icons / entry["file"]
    if not svg.is_file():
        raise SystemExit(f"missing svg for {icon_id}: {entry['file']}")
    data = svg.read_bytes()
    text = data.decode("utf-8")
    if len(data) > 1024:
        raise SystemExit(f"{entry['file']} exceeds 1KB")
    if 'viewBox="0 0 24 24"' not in text or "currentColor" not in text:
        raise SystemExit(f"{entry['file']} missing viewBox or currentColor")
PY
printf 'frontend assets OK\n'
