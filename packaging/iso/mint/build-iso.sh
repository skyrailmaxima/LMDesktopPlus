#!/usr/bin/env bash
# Scripted, reproducible Linux Mint respin for LMDesktopPlus.
#
# Assembles a live-build configuration that preinstalls the
# lmdesktopplus-desktop metapackage (the full vapor//matrix software set) plus
# the LMDesktopPlus control center, seeds the default vapor//matrix look
# (wallpaper + dark dconf defaults), autostarts the UI at login, registers the
# optional Hyprland session, and applies trademark-safe custom branding.
#
# Modes:
#   --check     (default) Build the two .debs, assemble + validate the staging
#               live-build config tree. Runs fully on this Linux cloud agent;
#               needs no root and no /dev/kvm.
#   --dry-run   Same as --check, then print the exact `lb` commands that the
#               real build would run (still no lb invocation).
#   --build     Assemble, then run `lb config` + `lb build` to emit the ISO.
#               Requires root and the live-build package (`lb`). Boot-test the
#               result on the KVM Mint lab (see docs/vm-lab.md); this cloud
#               agent has no /dev/kvm so --build is gated to a proper host.
#
# Output (on --build): dist/lmdesktopplus-mint-<ver>.iso
#
# Base/mirror are configurable via env for the live-build bootstrap
# (Mint tracks an Ubuntu LTS base; Cubic on a Mint ISO is the documented
# interactive fallback in packaging/iso/mint/README.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HERE="$ROOT/packaging/iso/mint"
CONFIG_SRC="$HERE/config"

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

# Live-build bootstrap knobs (overridable). Mint 22.x tracks Ubuntu 24.04.
LB_DISTRIBUTION="${LB_DISTRIBUTION:-noble}"
LB_ARCHIVE_AREAS="${LB_ARCHIVE_AREAS:-main restricted universe multiverse}"
LB_MIRROR="${LB_MIRROR:-http://archive.ubuntu.com/ubuntu/}"

STAGE="${STAGE:-$ROOT/build/iso/mint}"
STAGE_CONFIG="$STAGE/config"
DIST="$ROOT/dist"
ISO_OUT="$DIST/lmdesktopplus-mint-${VERSION}.iso"

say() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- canonical sources -------------------------------------------------------
WALLPAPER_PNG="$ROOT/assets/wallpapers/vapor-matrix.png"
WALLPAPER_SVG="$ROOT/assets/wallpapers/vapor-matrix.svg"
HYPR_SESSION="$ROOT/packages/hyprland/sessions/lmdesktopplus-hyprland.desktop"
AUTOSTART="$ROOT/share/xdg-autostart/lmdesktopplus.desktop"

for f in "$WALLPAPER_PNG" "$HYPR_SESSION" "$AUTOSTART" \
         "$CONFIG_SRC/includes.chroot/etc/dconf/profile/user" \
         "$CONFIG_SRC/includes.chroot/etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix" \
         "$CONFIG_SRC/includes.chroot/etc/lmdesktopplus/spin-release" \
         "$CONFIG_SRC/hooks/normal/50-lmdesktopplus.hook.chroot"; do
  [[ -e "$f" ]] || die "missing required source: $f"
done

# --- build the payload .debs -------------------------------------------------
say "==> Building LMDesktopPlus .debs (control center + desktop metapackage)"
DEB_APP="$(cd "$ROOT" && ./packaging/build-deb.sh)"
DEB_META="$(cd "$ROOT" && ./packaging/build-deb-metapackage.sh)"
[[ -f "$DEB_APP" ]]  || die "control-center .deb not produced ($DEB_APP)"
[[ -f "$DEB_META" ]] || die "metapackage .deb not produced ($DEB_META)"
say "    app:  $DEB_APP"
say "    meta: $DEB_META"

# --- assemble the live-build staging config ---------------------------------
say "==> Assembling live-build staging config at $STAGE_CONFIG"
rm -rf "$STAGE_CONFIG"
mkdir -p "$STAGE_CONFIG"
# Committed customization (dconf defaults, branding marker, finalize hook).
cp -a "$CONFIG_SRC/." "$STAGE_CONFIG/"

# Bundle the two locally-built .debs; live-build installs packages.chroot debs
# and resolves their dependencies (the full software set) from the archive.
mkdir -p "$STAGE_CONFIG/packages.chroot"
cp -a "$DEB_APP"  "$STAGE_CONFIG/packages.chroot/"
cp -a "$DEB_META" "$STAGE_CONFIG/packages.chroot/"

# Inject the branded assets into the chroot overlay.
BG_DIR="$STAGE_CONFIG/includes.chroot/usr/share/backgrounds/lmdesktopplus"
SESS_DIR="$STAGE_CONFIG/includes.chroot/usr/share/wayland-sessions"
AUTOSTART_DIR="$STAGE_CONFIG/includes.chroot/etc/xdg/autostart"
mkdir -p "$BG_DIR" "$SESS_DIR" "$AUTOSTART_DIR"
cp -a "$WALLPAPER_PNG" "$BG_DIR/vapor-matrix.png"
[[ -e "$WALLPAPER_SVG" ]] && cp -a "$WALLPAPER_SVG" "$BG_DIR/vapor-matrix.svg"
cp -a "$HYPR_SESSION" "$SESS_DIR/lmdesktopplus-hyprland.desktop"
cp -a "$AUTOSTART" "$AUTOSTART_DIR/lmdesktopplus.desktop"

# live-build requires hooks to be executable.
chmod 0755 "$STAGE_CONFIG/hooks/normal/50-lmdesktopplus.hook.chroot"

# --- validate the assembled layout ------------------------------------------
say "==> Validating staging layout"
expect=(
  "packages.chroot/$(basename "$DEB_APP")"
  "packages.chroot/$(basename "$DEB_META")"
  "includes.chroot/usr/share/backgrounds/lmdesktopplus/vapor-matrix.png"
  "includes.chroot/usr/share/wayland-sessions/lmdesktopplus-hyprland.desktop"
  "includes.chroot/etc/xdg/autostart/lmdesktopplus.desktop"
  "includes.chroot/etc/dconf/profile/user"
  "includes.chroot/etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix"
  "includes.chroot/etc/lmdesktopplus/spin-release"
  "hooks/normal/50-lmdesktopplus.hook.chroot"
)
for rel in "${expect[@]}"; do
  [[ -e "$STAGE_CONFIG/$rel" ]] || die "assembled config missing $rel"
done
[[ -x "$STAGE_CONFIG/hooks/normal/50-lmdesktopplus.hook.chroot" ]] \
  || die "hook is not executable"
# The autostart entry must actually launch the control center.
grep -q '^Exec=lmdesktopplus' "$AUTOSTART_DIR/lmdesktopplus.desktop" \
  || die "autostart entry does not Exec lmdesktopplus"
# The dconf default must point at the branded wallpaper we injected.
grep -q 'backgrounds/lmdesktopplus/vapor-matrix.png' \
  "$STAGE_CONFIG/includes.chroot/etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix" \
  || die "dconf default does not reference the injected wallpaper"
say "    layout OK ($(find "$STAGE_CONFIG" -type f | wc -l) files staged)"

lb_plan() {
  cat <<PLAN
(cd "$STAGE" && lb config \\
    --distribution "$LB_DISTRIBUTION" \\
    --archive-areas "$LB_ARCHIVE_AREAS" \\
    --mirror-bootstrap "$LB_MIRROR" \\
    --debian-installer none \\
    --iso-application "LMDesktopPlus Spin" \\
    --iso-volume "LMDesktopPlus ${VERSION}")
(cd "$STAGE" && lb build)
# then: mv "$STAGE"/live-image-*.iso "$ISO_OUT"
PLAN
}

case "$MODE" in
  check)
    say "==> --check OK: staging config assembled and validated."
    say "    Run with --build on a host with root + live-build (\`lb\`) to emit:"
    say "    $ISO_OUT"
    ;;
  dry-run)
    say "==> --dry-run: the real build would run:"
    lb_plan
    ;;
  build)
    command -v lb >/dev/null 2>&1 || die "live-build (lb) not installed; install 'live-build' on the builder host"
    [[ "$(id -u)" -eq 0 ]] || die "lb build must run as root"
    mkdir -p "$DIST"
    say "==> Running live-build (this bootstraps a full base system)"
    ( cd "$STAGE" && lb config \
        --distribution "$LB_DISTRIBUTION" \
        --archive-areas "$LB_ARCHIVE_AREAS" \
        --mirror-bootstrap "$LB_MIRROR" \
        --debian-installer none \
        --iso-application "LMDesktopPlus Spin" \
        --iso-volume "LMDesktopPlus ${VERSION}" )
    ( cd "$STAGE" && lb build )
    built="$(find "$STAGE" -maxdepth 1 -name 'live-image-*.iso' | head -n1)"
    [[ -n "$built" ]] || die "lb build did not produce an ISO"
    mv "$built" "$ISO_OUT"
    say "==> ISO: $ISO_OUT"
    ;;
esac
