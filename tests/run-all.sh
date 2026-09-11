#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$*"; }

step "smoke structure"
./tests/smoke-structure.sh

step "common helpers"
./tests/test-common.sh

step "frontend assets"
./tests/frontend-assets.sh

step "stow mode"
./tests/stow-mode.sh

step "vm lab scripts (dry-run gates)"
./tests/test-vm-scripts.sh

step "python compile + unit tests"
python3 -m compileall -q src/lmdesktopplus
PYTHONPATH=src python3 -m unittest discover -s tests/python -v

if command -v node >/dev/null 2>&1; then
  step "node syntax checks"
  node --check src/lmdesktopplus/static/digitalvapor.js
  node --check src/lmdesktopplus/static/bindings.js
  node --check src/lmdesktopplus/static/store.js
  node --check src/lmdesktopplus/static/app.js

  step "node behaviour tests"
  node tests/js/reduced-motion.test.js
else
  printf 'note: node not found; skipping JS syntax checks\n' >&2
fi

step "ui screenshot smoke (optional)"
if command -v Xvfb >/dev/null 2>&1 && command -v xdotool >/dev/null 2>&1 \
   && PYTHONPATH=src python3 -c 'import sys; from lmdesktopplus.toolkit import select_toolkit; sys.exit(0 if select_toolkit() else 1)' >/dev/null 2>&1; then
  ./tests/ui-screenshot.sh --out /tmp/lmdesktopplus-ui-screenshots
else
  printf 'note: Xvfb/xdotool/GTK+WebKit not all present; skipping UI screenshot smoke\n' >&2
fi

step "installer dry-run (cinnamon-only)"
./install.sh --dry-run --cinnamon-only >/tmp/lmdesktopplus-dry-run.log 2>&1

step "Debian package"
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
grep -q 'store.js' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.svg' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.png' "$DEB_CONTENTS"
grep -q 'usr/share/lmdesktopplus/autostart/lmdesktopplus.desktop' "$DEB_CONTENTS"

step "FreeBSD UI package stage"
./packaging/build-freebsd-ui.sh >/tmp/lmdesktopplus-freebsd-path.txt
FREEBSD_PATH="$(cat /tmp/lmdesktopplus-freebsd-path.txt)"
FREEBSD_LIST="/tmp/lmdesktopplus-freebsd-contents.txt"
tar -tJf "$FREEBSD_PATH" > "$FREEBSD_LIST"
if grep -E '^(\./)?plist$' "$FREEBSD_LIST"; then
  echo "FreeBSD tarball contains root-level plist (would install as /plist)" >&2
  exit 1
fi
grep -q 'usr/local/bin/lmdesktopplus' "$FREEBSD_LIST"
grep -q 'usr/local/lib/lmdesktopplus/lmdesktopplus/' "$FREEBSD_LIST"
grep -q 'usr/local/share/doc/lmdesktopplus/freebsd-ui.md' "$FREEBSD_LIST"
grep -q 'usr/local/share/doc/lmdesktopplus/plist' "$FREEBSD_LIST"
grep -q 'usr/local/share/lmdesktopplus/autostart/lmdesktopplus.desktop' "$FREEBSD_LIST"

step "collapse-stack dry-run"
./scripts/collapse-stack.sh >/tmp/lmdesktopplus-collapse-plan.txt

printf 'all tests OK\n'
