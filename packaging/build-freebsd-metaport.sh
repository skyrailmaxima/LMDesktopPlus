#!/usr/bin/env bash
# Generates the lmdesktopplus-desktop FreeBSD metaport (x11-wm/lmdesktopplus-desktop)
# from the canonical software manifest. The metaport installs no files; it just
# RUN_DEPENDS on the LMDesktopPlus UI port plus the full vapor//matrix peer set,
# so `pkg install lmdesktopplus-desktop` from the poudriere repo pulls
# everything. Runs anywhere (pure text generation); actually *building* it needs
# a FreeBSD ports tree / poudriere (see packaging/freebsd/poudriere/).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Unable to read project version" >&2; exit 1; }

MANIFEST="$ROOT/packaging/manifest.py"
ORIGINS="$ROOT/packaging/freebsd/pkg-origins.json"
OUT="${1:-$ROOT/build/freebsd-metaport}"

# RUN_DEPENDS: the UI port first, then every peer from the manifest. This fails
# if any FreeBSD package lacks an origin mapping (keeps the map in sync).
mapfile -t DEPS < <(python3 "$MANIFEST" freebsd-run-depends --origins "$ORIGINS")
[[ "${#DEPS[@]}" -gt 0 ]] || { echo "manifest produced no FreeBSD run-depends" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"

# Assemble the RUN_DEPENDS block with ports-style tab indentation + line
# continuations (UI port first).
run_depends_block() {
  printf 'RUN_DEPENDS=\tlmdesktopplus>0:x11-wm/lmdesktopplus'
  local dep
  for dep in "${DEPS[@]}"; do
    printf ' \\\n\t\t%s' "$dep"
  done
  printf '\n'
}

{
  printf 'PORTNAME=\tlmdesktopplus-desktop\n'
  printf 'DISTVERSION=\t%s\n' "$VERSION"
  printf 'CATEGORIES=\tx11-wm\n\n'
  printf 'MAINTAINER=\tlmdesktopplus@localhost\n'
  printf 'COMMENT=\tFull vapor//matrix desktop metaport (LMDesktopPlus + peers)\n'
  printf 'WWW=\t\thttps://github.com/skyrailmaxima/LMDesktopPlus\n\n'
  printf 'LICENSE=\tMIT\n\n'
  printf '# Generated from packaging/software-manifest.json by\n'
  printf '# packaging/build-freebsd-metaport.sh -- edit the manifest, not this file.\n'
  run_depends_block
  printf '\n'
  printf 'USES=\t\tmetaport\n'
  printf 'NO_ARCH=\tyes\n\n'
  printf '.include <bsd.port.mk>\n'
} > "$OUT/Makefile"

cat > "$OUT/pkg-descr" <<'DESCR'
Full vapor//matrix desktop metaport for FreeBSD.

Installs the LMDesktopPlus control center (x11-wm/lmdesktopplus) together with
the complete peer software set the UI drives: terminals, launcher, monitors,
media, screenshot/clipboard tools, the optional Hyprland session, and the
primary UI font. Installs no files itself.

Linux-only peers (NetworkManager, bubblewrap, BlueZ, Mint Update) are omitted;
the UI degrades fail-soft when a peer is absent.
DESCR

printf '%s\n' "$OUT/Makefile"
