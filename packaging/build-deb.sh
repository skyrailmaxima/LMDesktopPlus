#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Unable to read project version" >&2; exit 1; }
ARCH="all"
PKG="lmdesktopplus"
BUILD="$ROOT/build/deb/${PKG}_${VERSION}_${ARCH}"
OUT="$ROOT/dist/${PKG}_${VERSION}_${ARCH}.deb"
rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" "$BUILD/usr/lib/lmdesktopplus" "$BUILD/usr/bin" \
  "$BUILD/usr/share/applications" "$BUILD/usr/share/icons/hicolor/scalable/apps" \
  "$BUILD/usr/share/doc/lmdesktopplus" "$ROOT/dist"
cp -a "$ROOT/src/lmdesktopplus" "$BUILD/usr/lib/lmdesktopplus/lmdesktopplus"
mkdir -p "$BUILD/usr/lib/lmdesktopplus/assets"
cp -a "$ROOT/assets/wallpapers" "$BUILD/usr/lib/lmdesktopplus/assets/wallpapers"
find "$BUILD/usr/lib/lmdesktopplus/lmdesktopplus" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$BUILD/usr/lib/lmdesktopplus/lmdesktopplus" -type f -name '*.py[co]' -delete
cp -a "$ROOT/share/applications/lmdesktopplus.desktop" "$BUILD/usr/share/applications/lmdesktopplus.desktop"
cp -a "$ROOT/share/icons/hicolor/scalable/apps/lmdesktopplus.svg" "$BUILD/usr/share/icons/hicolor/scalable/apps/lmdesktopplus.svg"
cp -a "$ROOT/README.md" "$BUILD/usr/share/doc/lmdesktopplus/README.md"
cp -a "$ROOT/docs/machine-ui.md" "$BUILD/usr/share/doc/lmdesktopplus/machine-ui.md"
cp -a "$ROOT/docs/digitalvapor-design-system.md" "$BUILD/usr/share/doc/lmdesktopplus/digitalvapor-design-system.md"
gzip -9cn "$ROOT/CHANGELOG.md" > "$BUILD/usr/share/doc/lmdesktopplus/changelog.gz"
cat > "$BUILD/usr/share/doc/lmdesktopplus/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: LMDesktopPlus
Source: https://github.com/skyrailmaxima/LMDesktopPlus

Files: *
Copyright: 2026 skyrailmaxima and LMDesktopPlus contributors
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
COPYRIGHT
cat > "$BUILD/usr/bin/lmdesktopplus" <<'WRAPPER'
#!/usr/bin/env sh
PYTHONPATH=/usr/lib/lmdesktopplus exec python3 -m lmdesktopplus "$@"
WRAPPER
chmod 0755 "$BUILD/usr/bin/lmdesktopplus"
cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: lmdesktopplus
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: LMDesktopPlus contributors
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0, network-manager
Recommends: kitty, rofi, tmux, btop, playerctl, bubblewrap
Suggests: hyprland, waybar, bluez, starship, policykit-1, grim, slurp, wl-clipboard, xclip, libnotify-bin, mintupdate, cups-client, system-config-printer, swayidle
Description: Digitalvapor machine UI for Linux Mint
 A local vapor//matrix control center for real system metrics, application launchers,
 persistent appearance settings, NetworkManager, media controls, scoped agent
 workspaces, and an app vault that can pkexec-install allowlisted Suggests.
 It complements the LMDesktopPlus Cinnamon/Hyprland rice.
CONTROL
cat > "$BUILD/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database /usr/share/applications >/dev/null 2>&1 || true; fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true; fi
exit 0
POSTINST
chmod 0755 "$BUILD/DEBIAN/postinst"
dpkg-deb --root-owner-group --build "$BUILD" "$OUT" >/dev/null
printf '%s\n' "$OUT"
