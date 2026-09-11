#!/usr/bin/env sh
# Stand up a local poudriere pkg repo containing LMDesktopPlus, the
# lmdesktopplus-desktop metaport, and their peer set, so a FreeBSD install image
# (Phase 6) can `pkg install lmdesktopplus-desktop` from a self-hosted repo.
#
# This MUST run on a FreeBSD host with poudriere installed (pkg install
# poudriere). On any other OS it prints the plan and exits 0 so CI/dev boxes can
# lint it without a FreeBSD builder.
#
# Env overrides:
#   JAIL=lmdp           poudriere jail name
#   JAIL_VERSION=14.2-RELEASE
#   PORTS=lmdp          poudriere ports tree name
#   OVERLAY=/usr/local/poudriere-overlay   local ports overlay for our ports
#   REPO_OUT=/usr/local/lmdp-pkgrepo        where the built repo is published
set -eu

JAIL="${JAIL:-lmdp}"
JAIL_VERSION="${JAIL_VERSION:-14.2-RELEASE}"
PORTS="${PORTS:-lmdp}"
OVERLAY="${OVERLAY:-/usr/local/poudriere-overlay}"
REPO_OUT="${REPO_OUT:-/usr/local/lmdp-pkgrepo}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

plan() {
  cat <<PLAN
poudriere local pkg repo plan (run on FreeBSD):

  1. Overlay our ports into \$OVERLAY:
       x11-wm/lmdesktopplus            (from packaging/freebsd/Makefile)
       x11-wm/lmdesktopplus-desktop    (generated metaport)
  2. Create jail + ports tree (once):
       poudriere jail   -c -j $JAIL -v $JAIL_VERSION
       poudriere ports  -c -p $PORTS
  3. Build both ports with the overlay:
       poudriere bulk -j $JAIL -p $PORTS -O $OVERLAY \\
         x11-wm/lmdesktopplus x11-wm/lmdesktopplus-desktop
  4. Publish the repo (poudriere writes a pkg(8) repo under its data dir):
       ln -s /usr/local/poudriere/data/packages/${JAIL}-${PORTS} $REPO_OUT
  5. Consumers add it:
       echo 'lmdp: { url: "file://$REPO_OUT", enabled: yes }' \\
         > /usr/local/etc/pkg/repos/lmdp.conf
       pkg install lmdesktopplus-desktop
PLAN
}

if [ "$(uname -s)" != "FreeBSD" ]; then
  echo "==> not FreeBSD ($(uname -s)); printing plan only (no build performed)" >&2
  plan
  exit 0
fi

command -v poudriere >/dev/null 2>&1 || { echo "poudriere not installed: pkg install poudriere" >&2; exit 2; }

echo "==> staging local ports overlay in $OVERLAY"
mkdir -p "$OVERLAY/x11-wm/lmdesktopplus" "$OVERLAY/x11-wm/lmdesktopplus-desktop"
cp -R "$ROOT/packaging/freebsd/Makefile" "$ROOT/packaging/freebsd/pkg-descr" \
      "$ROOT/packaging/freebsd/pkg-message" "$ROOT/packaging/freebsd/files" \
      "$OVERLAY/x11-wm/lmdesktopplus/" 2>/dev/null || true

echo "==> generating metaport into the overlay"
sh "$ROOT/packaging/build-freebsd-metaport.sh" "$OVERLAY/x11-wm/lmdesktopplus-desktop" >/dev/null

echo "==> ensuring jail + ports tree"
poudriere jail  -l | grep -q "^$JAIL\b"  || poudriere jail  -c -j "$JAIL" -v "$JAIL_VERSION"
poudriere ports -l | grep -q "^$PORTS\b" || poudriere ports -c -p "$PORTS"

echo "==> building ports"
poudriere bulk -j "$JAIL" -p "$PORTS" -O "$OVERLAY" \
  x11-wm/lmdesktopplus x11-wm/lmdesktopplus-desktop

echo "==> repo built under poudriere data dir; symlinking to $REPO_OUT"
ln -sfn "/usr/local/poudriere/data/packages/${JAIL}-${PORTS}" "$REPO_OUT"
echo "done: add file://$REPO_OUT to /usr/local/etc/pkg/repos and pkg install lmdesktopplus-desktop"
