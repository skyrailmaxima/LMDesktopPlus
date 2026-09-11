#!/usr/bin/env bash
# Gate test for the FreeBSD install image: exercises build-image.sh --check
# (assembles + validates the poudriere-image overlay and package list) and
# asserts the committed autostart/branding/repo wiring. No FreeBSD/poudriere/
# root needed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_IMG="$ROOT/packaging/freebsd/image/build-image.sh"
IMGDIR="$ROOT/packaging/freebsd/image"
fail=0

pass() { printf 'OK  %s\n' "$*"; }
bad()  { printf 'FAIL %s\n' "$*"; fail=1; }

# Shell syntax on the orchestrator + shipped scripts.
bash -n "$BUILD_IMG" && pass "build-image.sh parses" || bad "build-image.sh syntax"
for s in \
  "overlay/usr/local/etc/rc.d/lmdp_autologin" \
  "overlay/root/.xinitrc" \
  "overlay/root/.profile"; do
  sh -n "$IMGDIR/$s" && pass "$s parses" || bad "$s syntax"
done

# Package list preinstalls the metapackage + the X/session stack.
PKGLIST="$IMGDIR/packages.list"
grep -q '^lmdesktopplus-desktop$' "$PKGLIST" && pass "preinstalls lmdesktopplus-desktop" || bad "missing metapackage in package list"
for p in xorg xinit dbus; do
  grep -q "^$p$" "$PKGLIST" && pass "package list has $p" || bad "package list missing $p"
done

# Local pkg repo config points at the Phase 4 poudriere repo.
grep -q 'file:///usr/local/lmdp-pkgrepo' "$IMGDIR/overlay/usr/local/etc/pkg/repos/lmdp.conf" \
  && pass "pkg repo config targets local poudriere repo" || bad "pkg repo config wrong"

# firstboot rc.d hook is a firstboot keyword script.
grep -q 'KEYWORD: firstboot' "$IMGDIR/overlay/usr/local/etc/rc.d/lmdp_autologin" \
  && pass "autologin hook is firstboot" || bad "autologin hook missing firstboot keyword"

# Branding marker present + trademark-safe (custom name, no os-release edit).
grep -q 'SPIN_NAME=' "$IMGDIR/overlay/etc/lmdesktopplus/spin-release" \
  && pass "spin branding marker present" || bad "spin branding marker missing"

# --check assembles + validates the overlay.
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT
if "$BUILD_IMG" --check >"$LOG" 2>&1; then
  pass "build-image.sh --check succeeds"
else
  bad "build-image.sh --check failed"; sed 's/^/    /' "$LOG"
fi

# Assembled overlay has the firstboot sentinel, injected wallpaper, and the
# Exec-rewritten autostart entry.
STAGE_OVERLAY="${STAGE:-$ROOT/build/freebsd-image}/overlay"
for rel in \
  "firstboot" \
  "usr/local/share/backgrounds/lmdesktopplus/vapor-matrix.png" \
  "usr/local/etc/xdg/autostart/lmdesktopplus.desktop"; do
  [[ -e "$STAGE_OVERLAY/$rel" ]] && pass "staged $rel" || bad "not staged: $rel"
done
grep -q '^Exec=/usr/local/bin/lmdesktopplus' \
  "$STAGE_OVERLAY/usr/local/etc/xdg/autostart/lmdesktopplus.desktop" \
  && pass "autostart Exec rewritten to pkg path" || bad "autostart Exec not rewritten"
grep -q 'lmdesktopplus' "$STAGE_OVERLAY/root/.xinitrc" \
  && pass ".xinitrc launches the UI" || bad ".xinitrc missing UI launch"

# --dry-run prints the gated poudriere image plan without invoking it.
if "$BUILD_IMG" --dry-run 2>&1 | grep -q 'poudriere image'; then
  pass "dry-run prints poudriere image plan"
else
  bad "dry-run missing poudriere image plan"
fi

[[ "$fail" -eq 0 ]] && printf 'freebsd-image tests OK\n' || { printf 'freebsd-image tests FAILED\n' >&2; exit 1; }
