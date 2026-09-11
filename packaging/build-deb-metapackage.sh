#!/usr/bin/env bash
# Builds the lmdesktopplus-desktop Debian metapackage: it carries no payload and
# Depends on the LMDesktopPlus control center plus the complete vapor//matrix
# software set from packaging/software-manifest.json. Preinstalling this single
# metapackage on the Mint respin (Phase 5) pulls everything.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Unable to read project version" >&2; exit 1; }

MANIFEST="$ROOT/packaging/manifest.py"
SET_DEPENDS="$(python3 "$MANIFEST" deb-metapackage-depends)"
[[ -n "$SET_DEPENDS" ]] || { echo "manifest produced no metapackage depends" >&2; exit 1; }
# The metapackage pins the control center itself, then the full peer set.
DEPENDS="lmdesktopplus (>= $VERSION), $SET_DEPENDS"

ARCH="all"
PKG="lmdesktopplus-desktop"
BUILD="$ROOT/build/deb/${PKG}_${VERSION}_${ARCH}"
OUT="$ROOT/dist/${PKG}_${VERSION}_${ARCH}.deb"
rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" "$BUILD/usr/share/doc/$PKG" "$ROOT/dist"

gzip -9cn "$ROOT/CHANGELOG.md" > "$BUILD/usr/share/doc/$PKG/changelog.gz"
cp -a "$ROOT/docs/software-manifest.md" "$BUILD/usr/share/doc/$PKG/software-manifest.md"
cat > "$BUILD/usr/share/doc/$PKG/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: LMDesktopPlus
Source: https://github.com/skyrailmaxima/LMDesktopPlus

Files: *
Copyright: 2026 skyrailmaxima and LMDesktopPlus contributors
License: MIT
COPYRIGHT

cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: metapackages
Priority: optional
Architecture: $ARCH
Maintainer: LMDesktopPlus contributors
Depends: $DEPENDS
Description: LMDesktopPlus vapor//matrix desktop (full software set)
 Metapackage that installs the LMDesktopPlus control center together with the
 complete vapor//matrix software set: terminals, launcher, monitors, media,
 network/bluetooth, screenshot/clipboard tools, the optional Hyprland session,
 and the primary UI font. Installing this one package is equivalent to
 preinstalling the whole desktop, which is how the Mint respin bakes it in.
 .
 OFL display fonts (DotGothic16, Zen Dots) are fetched by scripts/fetch-fonts.sh
 and are not packaged, so they are seeded separately by the respin.
CONTROL

dpkg-deb --root-owner-group --build "$BUILD" "$OUT" >/dev/null
printf '%s\n' "$OUT"
