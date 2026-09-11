#!/usr/bin/env bash
# Scripted, reproducible FreeBSD install image for LMDesktopPlus.
#
# Builds a bootable FreeBSD image that comes up into the vapor//matrix control
# center: it preinstalls the lmdesktopplus-desktop metapackage (UI + full peer
# set) from the Phase 4 local poudriere pkg repo plus the Xorg/GTK/WebKit stack,
# seeds the branded wallpaper + spin identity, and autostarts the UI on the
# primary console (ttyv0 autologin -> startx -> control center).
#
# The actual image build uses `poudriere image` (the modern, reproducible route
# that ties into the Phase 4 poudriere repo). `release(7)` / `mkimg` are the
# documented alternatives (see README.md); either way the build MUST run on a
# FreeBSD host and cannot run on this Linux cloud agent.
#
# Modes:
#   --check     (default) Assemble + validate the poudriere-image overlay and
#               package list. Runs on any host (incl. this Linux agent); no
#               FreeBSD, poudriere, or root required.
#   --dry-run   Same as --check, then print the exact `poudriere image` command.
#   --build     Run `poudriere image` to emit the image. Requires FreeBSD +
#               poudriere + root, and the local pkg repo from
#               packaging/freebsd/poudriere/build-repo.sh.
#
# Output (on --build): dist/lmdesktopplus-freebsd-<ver>.img
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$ROOT/packaging/freebsd/image"
OVERLAY_SRC="$HERE/overlay"
PKGLIST_SRC="$HERE/packages.list"

VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
[[ -n "$VERSION" ]] || { echo "Unable to read project version" >&2; exit 1; }

MODE="check"
case "${1:-}" in
  --check|"") MODE="check" ;;
  --dry-run)  MODE="dry-run" ;;
  --build)    MODE="build" ;;
  -h|--help)
    sed -n '1,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  *) echo "unknown argument: $1 (use --check | --dry-run | --build)" >&2; exit 2 ;;
esac

# poudriere image knobs (overridable).
JAIL="${JAIL:-lmdp}"
PORTS="${PORTS:-lmdp}"
IMG_TYPE="${IMG_TYPE:-usb}"          # usb | iso | iso+zmfs | ...
IMG_SIZE="${IMG_SIZE:-6g}"
IMG_HOST="${IMG_HOST:-lmdesktopplus}"
IMG_NAME="lmdesktopplus-freebsd-${VERSION}"

STAGE="${STAGE:-$ROOT/build/freebsd-image}"
STAGE_OVERLAY="$STAGE/overlay"
STAGE_PKGLIST="$STAGE/packages.list"
DIST="$ROOT/dist"
IMG_OUT="$DIST/${IMG_NAME}.img"

say() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- canonical sources -------------------------------------------------------
WALLPAPER_PNG="$ROOT/assets/wallpapers/vapor-matrix.png"
WALLPAPER_SVG="$ROOT/assets/wallpapers/vapor-matrix.svg"
AUTOSTART="$ROOT/share/xdg-autostart/lmdesktopplus.desktop"

for f in "$WALLPAPER_PNG" "$AUTOSTART" "$PKGLIST_SRC" \
         "$OVERLAY_SRC/usr/local/etc/pkg/repos/lmdp.conf" \
         "$OVERLAY_SRC/usr/local/etc/rc.d/lmdp_autologin" \
         "$OVERLAY_SRC/root/.xinitrc" \
         "$OVERLAY_SRC/root/.profile" \
         "$OVERLAY_SRC/etc/rc.conf.local" \
         "$OVERLAY_SRC/etc/lmdesktopplus/spin-release"; do
  [[ -e "$f" ]] || die "missing required source: $f"
done

# --- assemble the poudriere-image overlay -----------------------------------
say "==> Assembling poudriere-image overlay at $STAGE_OVERLAY"
rm -rf "$STAGE_OVERLAY"
mkdir -p "$STAGE_OVERLAY"
cp -a "$OVERLAY_SRC/." "$STAGE_OVERLAY/"

# firstboot sentinel so /usr/local/etc/rc.d/lmdp_autologin (KEYWORD: firstboot)
# runs on the first boot of the installed image.
: > "$STAGE_OVERLAY/firstboot"

# Inject the branded wallpaper.
BG_DIR="$STAGE_OVERLAY/usr/local/share/backgrounds/lmdesktopplus"
mkdir -p "$BG_DIR"
cp -a "$WALLPAPER_PNG" "$BG_DIR/vapor-matrix.png"
[[ -e "$WALLPAPER_SVG" ]] && cp -a "$WALLPAPER_SVG" "$BG_DIR/vapor-matrix.svg"

# Ship the XDG autostart entry too (used when a full desktop session is chosen
# instead of the default kiosk .xinitrc), with Exec pointed at the pkg path.
AUTOSTART_DIR="$STAGE_OVERLAY/usr/local/etc/xdg/autostart"
mkdir -p "$AUTOSTART_DIR"
sed -e 's#^Exec=.*#Exec=/usr/local/bin/lmdesktopplus#' \
    -e 's#^TryExec=.*#TryExec=/usr/local/bin/lmdesktopplus#' \
    "$AUTOSTART" > "$AUTOSTART_DIR/lmdesktopplus.desktop"

# rc.d scripts must be executable.
chmod 0555 "$STAGE_OVERLAY/usr/local/etc/rc.d/lmdp_autologin"
chmod 0644 "$STAGE_OVERLAY/root/.xinitrc" "$STAGE_OVERLAY/root/.profile"

# Copy the package list verbatim (single source of truth).
cp -a "$PKGLIST_SRC" "$STAGE_PKGLIST"

# --- validate the assembled overlay -----------------------------------------
say "==> Validating overlay layout"
expect=(
  "firstboot"
  "usr/local/etc/pkg/repos/lmdp.conf"
  "usr/local/etc/rc.d/lmdp_autologin"
  "usr/local/etc/xdg/autostart/lmdesktopplus.desktop"
  "usr/local/share/backgrounds/lmdesktopplus/vapor-matrix.png"
  "root/.xinitrc"
  "root/.profile"
  "etc/rc.conf.local"
  "etc/lmdesktopplus/spin-release"
)
for rel in "${expect[@]}"; do
  [[ -e "$STAGE_OVERLAY/$rel" ]] || die "assembled overlay missing $rel"
done
[[ -x "$STAGE_OVERLAY/usr/local/etc/rc.d/lmdp_autologin" ]] || die "rc.d hook not executable"
grep -q '^lmdesktopplus-desktop$' "$STAGE_PKGLIST" || die "package list must preinstall lmdesktopplus-desktop"
grep -q '^Exec=/usr/local/bin/lmdesktopplus' "$AUTOSTART_DIR/lmdesktopplus.desktop" \
  || die "autostart Exec not rewritten to the pkg path"
grep -q 'lmdesktopplus' "$STAGE_OVERLAY/root/.xinitrc" || die ".xinitrc does not launch the UI"
grep -q 'file:///usr/local/lmdp-pkgrepo' "$STAGE_OVERLAY/usr/local/etc/pkg/repos/lmdp.conf" \
  || die "pkg repo config does not point at the local poudriere repo"
# sh syntax on the shipped scripts.
sh -n "$STAGE_OVERLAY/usr/local/etc/rc.d/lmdp_autologin" || die "rc.d hook has a syntax error"
sh -n "$STAGE_OVERLAY/root/.xinitrc" || die ".xinitrc has a syntax error"
sh -n "$STAGE_OVERLAY/root/.profile" || die ".profile has a syntax error"
say "    layout OK ($(find "$STAGE_OVERLAY" -type f | wc -l) files staged)"

poudriere_plan() {
  cat <<PLAN
poudriere image \\
    -t "$IMG_TYPE" \\
    -j "$JAIL" -p "$PORTS" \\
    -h "$IMG_HOST" \\
    -n "$IMG_NAME" \\
    -s "$IMG_SIZE" \\
    -f "$STAGE_PKGLIST" \\
    -c "$STAGE_OVERLAY"
# then: mv <poudriere image output>.img "$IMG_OUT"
PLAN
}

case "$MODE" in
  check)
    say "==> --check OK: image overlay + package list assembled and validated."
    say "    Run with --build on a FreeBSD host (poudriere + root + local repo) to emit:"
    say "    $IMG_OUT"
    ;;
  dry-run)
    say "==> --dry-run: the real build would run:"
    poudriere_plan
    ;;
  build)
    [[ "$(uname -s)" == "FreeBSD" ]] || die "poudriere image must run on FreeBSD"
    command -v poudriere >/dev/null 2>&1 || die "poudriere not installed: pkg install poudriere"
    [[ "$(id -u)" -eq 0 ]] || die "poudriere image must run as root"
    mkdir -p "$DIST"
    say "==> Running poudriere image (bootstraps + populates a full image)"
    poudriere image \
      -t "$IMG_TYPE" \
      -j "$JAIL" -p "$PORTS" \
      -h "$IMG_HOST" \
      -n "$IMG_NAME" \
      -s "$IMG_SIZE" \
      -f "$STAGE_PKGLIST" \
      -c "$STAGE_OVERLAY"
    built="$(find /usr/local/poudriere/data/images -maxdepth 1 -name "${IMG_NAME}*.img" 2>/dev/null | head -n1)"
    [[ -n "$built" ]] || die "poudriere image did not produce ${IMG_NAME}*.img (check poudriere output)"
    mv "$built" "$IMG_OUT"
    say "==> Image: $IMG_OUT"
    ;;
esac
