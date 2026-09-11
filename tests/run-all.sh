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

step "ci workflow lint"
./tests/ci-workflow.sh

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
  node --check src/lmdesktopplus/static/tiles.js
  node --check src/lmdesktopplus/static/app.js

  step "node behaviour tests"
  node tests/js/reduced-motion.test.js
  node tests/js/greeting.test.js
  node tests/js/tiles.test.js
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

step "software manifest"
python3 packaging/manifest.py check

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
grep -q 'tiles.js' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.svg' "$DEB_CONTENTS"
grep -q 'usr/lib/lmdesktopplus/assets/wallpapers/vapor-matrix.png' "$DEB_CONTENTS"
grep -q 'usr/share/lmdesktopplus/autostart/lmdesktopplus.desktop' "$DEB_CONTENTS"

step "Debian desktop metapackage"
./packaging/build-deb-metapackage.sh >/tmp/lmdesktopplus-metadeb-path.txt
META_PATH="$(cat /tmp/lmdesktopplus-metadeb-path.txt)"
META_INFO="/tmp/lmdesktopplus-metadeb-info.txt"
dpkg-deb --info "$META_PATH" > "$META_INFO"
grep -q '^ Package: lmdesktopplus-desktop' "$META_INFO"
grep -Eq '^ Depends: lmdesktopplus \(>= ' "$META_INFO"
for pkg in kitty rofi hyprland fonts-jetbrains-mono swaybg; do
  grep -q "$pkg" "$META_INFO" || { echo "metapackage missing $pkg" >&2; exit 1; }
done
if dpkg-deb --contents "$META_PATH" | grep -q 'usr/lib/lmdesktopplus'; then
  echo "metapackage should not ship application payload" >&2
  exit 1
fi

step "FreeBSD desktop metaport"
META_MK="$(./packaging/build-freebsd-metaport.sh /tmp/lmdesktopplus-freebsd-metaport)"
grep -q '^PORTNAME=	lmdesktopplus-desktop$' "$META_MK"
grep -q 'USES=		metaport' "$META_MK"
grep -q 'lmdesktopplus>0:x11-wm/lmdesktopplus' "$META_MK"
for origin in x11/kitty www/webkit2-gtk@40 x11-wm/hyprland x11-fonts/jetbrains-mono; do
  grep -q "$origin" "$META_MK" || { echo "metaport missing origin $origin" >&2; exit 1; }
done
# Linux-only peers must not leak into the FreeBSD metaport.
if grep -Eq 'network-manager|bubblewrap|mintupdate' "$META_MK"; then
  echo "Linux-only peer leaked into FreeBSD metaport" >&2
  exit 1
fi
sh -n ./packaging/freebsd/poudriere/build-repo.sh

step "Mint respin ISO (staging assembly gate)"
./tests/iso-mint.sh

step "FreeBSD install image (overlay assembly gate)"
./tests/freebsd-image.sh

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
