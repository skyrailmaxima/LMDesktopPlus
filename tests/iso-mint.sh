#!/usr/bin/env bash
# Gate test for the Linux Mint respin: exercises build-iso.sh --check (which
# builds the .debs and assembles + validates the live-build staging config) and
# asserts the committed customization is well-formed. No root / lb / KVM needed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ISO="$ROOT/packaging/iso/mint/build-iso.sh"
CONFIG="$ROOT/packaging/iso/mint/config"
fail=0

pass() { printf 'OK  %s\n' "$*"; }
bad()  { printf 'FAIL %s\n' "$*"; fail=1; }

VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"

# Shell syntax + hook syntax.
bash -n "$BUILD_ISO" && pass "build-iso.sh parses" || bad "build-iso.sh syntax"
sh -n "$CONFIG/hooks/normal/50-lmdesktopplus.hook.chroot" \
  && pass "chroot hook parses" || bad "chroot hook syntax"

# Committed customization files exist.
for rel in \
  "includes.chroot/etc/dconf/profile/user" \
  "includes.chroot/etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix" \
  "includes.chroot/etc/lmdesktopplus/spin-release" \
  "hooks/normal/50-lmdesktopplus.hook.chroot"; do
  [[ -e "$CONFIG/$rel" ]] && pass "config has $rel" || bad "config missing $rel"
done

# dconf default points at the branded wallpaper and a dark look.
DCONF="$CONFIG/includes.chroot/etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix"
grep -q 'backgrounds/lmdesktopplus/vapor-matrix.png' "$DCONF" \
  && pass "dconf sets vapor-matrix wallpaper" || bad "dconf missing wallpaper"
grep -qi 'prefer-dark' "$DCONF" \
  && pass "dconf prefers dark color scheme" || bad "dconf missing dark scheme"

# Branding marker avoids Linux Mint trademarks and does not touch os-release.
grep -q 'SPIN_NAME=' "$CONFIG/includes.chroot/etc/lmdesktopplus/spin-release" \
  && pass "spin branding marker present" || bad "spin branding marker missing"

# --check builds the debs and assembles/validates the staging config.
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT
if "$BUILD_ISO" --check >"$LOG" 2>&1; then
  pass "build-iso.sh --check succeeds"
else
  bad "build-iso.sh --check failed"; sed 's/^/    /' "$LOG"
fi

# The assembled staging tree contains both bundled .debs and the branded assets.
STAGE_CONFIG="${STAGE:-$ROOT/build/iso/mint}/config"
for rel in \
  "packages.chroot/lmdesktopplus_${VERSION}_all.deb" \
  "packages.chroot/lmdesktopplus-desktop_${VERSION}_all.deb" \
  "includes.chroot/usr/share/backgrounds/lmdesktopplus/vapor-matrix.png" \
  "includes.chroot/usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop" \
  "includes.chroot/etc/xdg/autostart/lmdesktopplus.desktop"; do
  [[ -e "$STAGE_CONFIG/$rel" ]] && pass "staged $rel" || bad "not staged: $rel"
done

# Autostart launches the control center; hook is executable.
grep -q '^Exec=lmdesktopplus' \
  "$STAGE_CONFIG/includes.chroot/etc/xdg/autostart/lmdesktopplus.desktop" \
  && pass "autostart execs lmdesktopplus" || bad "autostart does not exec UI"
[[ -x "$STAGE_CONFIG/hooks/normal/50-lmdesktopplus.hook.chroot" ]] \
  && pass "staged hook is executable" || bad "staged hook not executable"

# --dry-run prints the gated lb plan without invoking lb.
if "$BUILD_ISO" --dry-run 2>&1 | grep -q 'lb build'; then
  pass "dry-run prints lb build plan"
else
  bad "dry-run missing lb build plan"
fi

[[ "$fail" -eq 0 ]] && printf 'iso-mint tests OK\n' || { printf 'iso-mint tests FAILED\n' >&2; exit 1; }
