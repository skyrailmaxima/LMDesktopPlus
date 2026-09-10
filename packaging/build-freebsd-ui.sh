#!/usr/bin/env bash
# Stage a FreeBSD-oriented UI package tarball (runs on Linux for dry packing).
# On FreeBSD, prefer the ports skeleton at packaging/freebsd/, or:
#   ./packaging/build-freebsd-ui.sh
#   sudo tar -xJf dist/lmdesktopplus-*-freebsd.txz -C /
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Unable to read project version" >&2; exit 1; }
PKG="lmdesktopplus"
STAGE="$ROOT/build/freebsd/${PKG}-${VERSION}"
OUT="$ROOT/dist/${PKG}-${VERSION}-freebsd.txz"
PREFIX="${PREFIX:-/usr/local}"

rm -rf "$STAGE"
mkdir -p \
  "$STAGE${PREFIX}/lib/lmdesktopplus" \
  "$STAGE${PREFIX}/bin" \
  "$STAGE${PREFIX}/share/applications" \
  "$STAGE${PREFIX}/share/icons/hicolor/scalable/apps" \
  "$STAGE${PREFIX}/share/doc/lmdesktopplus" \
  "$ROOT/dist"

cp -a "$ROOT/src/lmdesktopplus" "$STAGE${PREFIX}/lib/lmdesktopplus/lmdesktopplus"
mkdir -p "$STAGE${PREFIX}/lib/lmdesktopplus/assets"
if [[ -d "$ROOT/assets/wallpapers" ]]; then
  cp -a "$ROOT/assets/wallpapers" "$STAGE${PREFIX}/lib/lmdesktopplus/assets/wallpapers"
fi
find "$STAGE${PREFIX}/lib/lmdesktopplus/lmdesktopplus" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE${PREFIX}/lib/lmdesktopplus/lmdesktopplus" -type f -name '*.py[co]' -delete

cp -a "$ROOT/share/applications/lmdesktopplus.desktop" \
  "$STAGE${PREFIX}/share/applications/lmdesktopplus.desktop"
# Ports / FreeBSD layout uses /usr/local/bin.
if sed --version >/dev/null 2>&1; then
  sed -i \
    -e "s#^Exec=.*#Exec=${PREFIX}/bin/lmdesktopplus#" \
    -e "s#^TryExec=.*#TryExec=${PREFIX}/bin/lmdesktopplus#" \
    "$STAGE${PREFIX}/share/applications/lmdesktopplus.desktop"
else
  sed -i '' \
    -e "s#^Exec=.*#Exec=${PREFIX}/bin/lmdesktopplus#" \
    -e "s#^TryExec=.*#TryExec=${PREFIX}/bin/lmdesktopplus#" \
    "$STAGE${PREFIX}/share/applications/lmdesktopplus.desktop"
fi

# Autostart template (login autostart is enabled by the distro image, not here).
mkdir -p "$STAGE${PREFIX}/share/lmdesktopplus/autostart"
cp -a "$ROOT/share/xdg-autostart/lmdesktopplus.desktop" \
  "$STAGE${PREFIX}/share/lmdesktopplus/autostart/lmdesktopplus.desktop"

cp -a "$ROOT/share/icons/hicolor/scalable/apps/lmdesktopplus.svg" \
  "$STAGE${PREFIX}/share/icons/hicolor/scalable/apps/lmdesktopplus.svg"
cp -a "$ROOT/README.md" "$STAGE${PREFIX}/share/doc/lmdesktopplus/README.md"
cp -a "$ROOT/docs/machine-ui.md" "$STAGE${PREFIX}/share/doc/lmdesktopplus/machine-ui.md"
cp -a "$ROOT/docs/freebsd-ui.md" "$STAGE${PREFIX}/share/doc/lmdesktopplus/freebsd-ui.md"
cp -a "$ROOT/CHANGELOG.md" "$STAGE${PREFIX}/share/doc/lmdesktopplus/CHANGELOG.md"
cp -a "$ROOT/packaging/freebsd/pkg-message" \
  "$STAGE${PREFIX}/share/doc/lmdesktopplus/pkg-message"

cat > "$STAGE${PREFIX}/bin/lmdesktopplus" <<WRAPPER
#!/bin/sh
PYTHONPATH=${PREFIX}/lib/lmdesktopplus exec python3 -m lmdesktopplus "\$@"
WRAPPER
chmod 0755 "$STAGE${PREFIX}/bin/lmdesktopplus"

# File list for operators / ports pkg-plist generation (under PREFIX — never /plist).
(
  cd "$STAGE"
  find ".${PREFIX}" -type f | sed 's#^\./##' | sort
) > "$STAGE${PREFIX}/share/doc/lmdesktopplus/plist"

if command -v bsdtar >/dev/null 2>&1; then
  (cd "$STAGE" && bsdtar --uid 0 --gid 0 -cJf "$OUT" ".${PREFIX}")
else
  (cd "$STAGE" && tar -cJf "$OUT" ".${PREFIX}")
fi
printf '%s\n' "$OUT"
