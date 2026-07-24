#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
./tests/smoke-structure.sh
./tests/test-common.sh
./tests/frontend-assets.sh
python3 -m compileall -q src/lmdesktopplus
PYTHONPATH=src python3 -m unittest discover -s tests/python -v
if command -v node >/dev/null 2>&1; then
  node --check src/lmdesktopplus/static/digitalvapor.js
  node --check src/lmdesktopplus/static/bindings.js
  node --check src/lmdesktopplus/static/app.js
fi
./install.sh --dry-run --cinnamon-only >/tmp/lmdesktopplus-dry-run.log 2>&1
./packaging/build-deb.sh >/tmp/lmdesktopplus-deb-path.txt
DEB_PATH="$(cat /tmp/lmdesktopplus-deb-path.txt)"
dpkg-deb --info "$DEB_PATH" >/dev/null
DEB_CONTENTS="/tmp/lmdesktopplus-deb-contents.txt"
dpkg-deb --contents "$DEB_PATH" > "$DEB_CONTENTS"
if grep -Eq '(__pycache__|\.py[co]$)' "$DEB_CONTENTS"; then
  echo "bytecode cache leaked into Debian package" >&2
  exit 1
fi
if grep -Eqi '\.(woff2?|ttf|otf)$' "$DEB_CONTENTS"; then
  echo "font binary leaked into Debian package" >&2
  exit 1
fi
grep -q 'digitalvapor.css' "$DEB_CONTENTS"
grep -q 'digitalvapor.js' "$DEB_CONTENTS"
grep -q 'bindings.js' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.svg' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.png' "$DEB_CONTENTS"
printf 'all tests OK\n'
