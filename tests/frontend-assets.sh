#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC="$ROOT/src/lmdesktopplus/static"

grep -q -- '--dv-accent' "$STATIC/digitalvapor.css"
grep -q 'Digitalvapor' "$STATIC/digitalvapor.js"
grep -q 'digitalvapor.css' "$STATIC/index.html"
grep -q 'digitalvapor.js' "$STATIC/index.html"
if grep -Eq '<script[^>]*>[^<]*window\.LMDP_TOKEN' "$STATIC/index.html"; then
  echo "inline token script remains in index.html" >&2
  exit 1
fi
if find "$ROOT" -type f \( -iname '*.woff' -o -iname '*.woff2' -o -iname '*.ttf' -o -iname '*.otf' \) -print -quit | grep -q .; then
  echo "font binary leaked into source tree" >&2
  exit 1
fi
printf 'frontend assets OK\n'
