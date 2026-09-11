#!/usr/bin/env bash
# Headless per-scene screenshot smoke for the native LMDesktopPlus shell.
#
# Boots the embedded GTK/WebKit window under Xvfb, unlocks it, switches through
# each UI scene via its hotkey, captures a PNG per scene, and asserts every
# capture is a non-blank render (so a broken scene, a JS error, or a shell that
# fails to paint is caught in CI). Requires: Xvfb, xdotool, python3-gi + GTK3 +
# WebKit2, and a working software GL stack.
#
# Usage:
#   ./tests/ui-screenshot.sh [--out DIR] [--scenes "desktop monitor ..."]
#                            [--keep] [--display :N] [--geom WxHxD]
#                            [--window WxH]
#
# --geom drives the Xvfb screen size. --window pre-seeds the shell's saved
# window geometry (ui-state.json); use a narrow value (e.g. --window 700x880)
# to capture the responsive small-window layout, since there is no window
# manager to resize the mapped window for us.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="$ROOT/build/ui-screenshots"
SCENES="desktop terminal monitor apps settings kit"
KEEP=0
DISPLAY_NUM=""
GEOM="1366x900x24"
WINDOW=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --scenes) SCENES="$2"; shift 2 ;;
    --display) DISPLAY_NUM="$2"; shift 2 ;;
    --geom) GEOM="$2"; shift 2 ;;
    --window) WINDOW="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing dependency: $1" >&2; exit 3; }; }
need Xvfb
need xdotool
need python3

# Scene hotkeys mirror app.js (1-0 digits, k for the UI kit).
declare -A HOTKEY=(
  [desktop]=1 [terminal]=2 [tmux]=3 [editor]=4 [browser]=5 [rofi]=6
  [docs]=7 [monitor]=8 [apps]=9 [settings]=0 [kit]=k
)

mkdir -p "$OUT"

# Pick a free display unless the caller pinned one.
pick_display() {
  for n in 99 98 97 96 95; do
    [[ -e "/tmp/.X11-unix/X${n}" ]] || { echo ":${n}"; return; }
  done
  echo ":99"
}
[[ -n "$DISPLAY_NUM" ]] || DISPLAY_NUM="$(pick_display)"

# Isolated XDG dirs so we never touch the developer's real state or lock file.
WORKDIR="$(mktemp -d)"
export XDG_DATA_HOME="$WORKDIR/data"
export XDG_CONFIG_HOME="$WORKDIR/config"
export XDG_CACHE_HOME="$WORKDIR/cache"
export XDG_RUNTIME_DIR="$WORKDIR/run"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Pre-seed the saved window geometry so the shell restores a specific size.
# Without a window manager the mapped window keeps its own size regardless of
# the Xvfb screen, so this is how we exercise the responsive small-window CSS.
if [[ -n "$WINDOW" ]]; then
  WIN_W="${WINDOW%x*}"
  WIN_H="${WINDOW#*x}"
  mkdir -p "$XDG_DATA_HOME/lmdesktopplus"
  cat > "$XDG_DATA_HOME/lmdesktopplus/ui-state.json" <<JSON
{"scene":"desktop","window":{"width":${WIN_W},"height":${WIN_H},"maximized":false}}
JSON
fi

XVFB_PID=""
APP_PID=""
cleanup() {
  if [[ "$KEEP" -eq 0 ]]; then
    [[ -n "$APP_PID" ]] && kill "$APP_PID" 2>/dev/null || true
    [[ -n "$XVFB_PID" ]] && kill "$XVFB_PID" 2>/dev/null || true
    rm -rf "$WORKDIR"
  else
    echo "left running: DISPLAY=$DISPLAY_NUM  app_pid=$APP_PID  workdir=$WORKDIR"
  fi
}
trap cleanup EXIT

echo "==> Xvfb $DISPLAY_NUM ($GEOM)"
Xvfb "$DISPLAY_NUM" -screen 0 "$GEOM" -nolisten tcp >/dev/null 2>&1 &
XVFB_PID=$!
export DISPLAY="$DISPLAY_NUM"

# Wait for the X server socket.
for _ in $(seq 1 50); do
  xdotool getdisplaygeometry >/dev/null 2>&1 && break
  sleep 0.1
done

echo "==> launching native shell"
PYTHONPATH="$ROOT/src" python3 -m lmdesktopplus >"$WORKDIR/app.log" 2>&1 &
APP_PID=$!

# Wait for the shell window (proves the GTK/WebKit shell started at all).
WID=""
for _ in $(seq 1 100); do
  WID="$(xdotool search --class lmdesktopplus 2>/dev/null | head -1 || true)"
  [[ -n "$WID" ]] && break
  kill -0 "$APP_PID" 2>/dev/null || { echo "app exited early:"; cat "$WORKDIR/app.log" >&2; exit 4; }
  sleep 0.2
done
[[ -n "$WID" ]] || { echo "shell window never appeared" >&2; cat "$WORKDIR/app.log" >&2; exit 4; }
echo "    window id=$WID"

xdotool windowactivate --sync "$WID" 2>/dev/null || true

# Window center for the unlock click (no WM, so it usually maps at the origin).
eval "$(xdotool getwindowgeometry --shell "$WID" 2>/dev/null || echo 'X=0 Y=0 WIDTH=1320 HEIGHT=840')"
CX=$(( ${X:-0} + ${WIDTH:-1320} / 2 ))
CY=$(( ${Y:-0} + ${HEIGHT:-840} / 2 ))

# capture <path>: grab the root (clean under a dedicated Xvfb) into a PNG.
capture() {
  DISPLAY="$DISPLAY_NUM" python3 - "$1" <<'PY'
import sys, gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
root = Gdk.get_default_root_window()
pb = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
pb.savev(sys.argv[1], "png", [], [])
PY
}

# differs <a> <b>: exit 0 if the two PNGs differ meaningfully (proves the UI
# actually changed, e.g. unlock or a scene switch really happened).
differs() {
  DISPLAY="$DISPLAY_NUM" python3 - "$1" "$2" <<'PY'
import sys, gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
a = GdkPixbuf.Pixbuf.new_from_file(sys.argv[1]).get_pixels()
b = GdkPixbuf.Pixbuf.new_from_file(sys.argv[2]).get_pixels()
n = min(len(a), len(b))
step = max(1, n // 20000)
diffs = [abs(a[i] - b[i]) for i in range(0, n, step)]
mean = sum(diffs) / max(1, len(diffs))
sys.exit(0 if mean > 4 else 1)
PY
}

# nonblank <path>: exit 0 if the image has meaningful visual variance.
nonblank() {
  DISPLAY="$DISPLAY_NUM" python3 - "$1" <<'PY'
import sys, gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
pb = GdkPixbuf.Pixbuf.new_from_file(sys.argv[1])
data = pb.get_pixels()
step = max(1, len(data) // 20000)  # sample ~20k bytes
sample = data[::step]
lo, hi = min(sample), max(sample)
distinct = len(set(sample))
# A solid/blank frame has ~1 value; real UI has a wide spread.
sys.exit(0 if (hi - lo) > 24 and distinct > 12 else 1)
PY
}

fail=0

# Software WebKit rendering can lag; poll until the shell actually paints its
# first non-blank frame (the lock screen) before driving the UI.
painted=0
for _ in $(seq 1 60); do
  capture "$OUT/00-lock.png"
  if nonblank "$OUT/00-lock.png"; then painted=1; break; fi
  sleep 0.5
done
if [[ "$painted" -eq 1 ]]; then
  echo "OK   lock screen renders"
else
  echo "FAIL lock screen never painted" >&2; fail=1
fi

# The lock screen unlocks on a click anywhere; a real pointer click (XTEST)
# reaches WebKit where synthetic --window events do not. If the click misses
# (window mapped off the expected origin, etc.), fall back to the desktop
# hotkey via focus+key, which also unlocks and selects the desktop scene.
unlock_ok=0
xdotool mousemove "$CX" "$CY" click 1
sleep 1.5
capture "$OUT/01-desktop.png"
if nonblank "$OUT/01-desktop.png" && differs "$OUT/00-lock.png" "$OUT/01-desktop.png"; then
  unlock_ok=1
else
  xdotool windowfocus "$WID" 2>/dev/null || true
  xdotool key 1
  sleep 1.5
  capture "$OUT/01-desktop.png"
  if nonblank "$OUT/01-desktop.png" && differs "$OUT/00-lock.png" "$OUT/01-desktop.png"; then
    unlock_ok=1
  fi
fi
if [[ "$unlock_ok" -eq 1 ]]; then
  echo "OK   unlocked desktop renders (differs from lock screen)"
else
  echo "FAIL unlock did not render the desktop (still locked/blank?)" >&2; fail=1
fi

# Scene hotkeys need real input focus; xdotool key (XTEST) after windowfocus
# reaches the WebView, unlike synthetic --window key events.
i=1  # desktop already captured above as 01
for scene in $SCENES; do
  [[ "$scene" == "desktop" ]] && continue
  key="${HOTKEY[$scene]:-}"
  if [[ -z "$key" ]]; then echo "skip unknown scene: $scene" >&2; continue; fi
  i=$((i+1))
  xdotool windowfocus "$WID" 2>/dev/null || true
  xdotool key "$key"
  sleep 1.2
  path="$(printf '%s/%02d-%s.png' "$OUT" "$i" "$scene")"
  capture "$path"
  if nonblank "$path"; then
    echo "OK   scene '$scene' renders -> $path"
  else
    echo "FAIL scene '$scene' is blank -> $path" >&2; fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  echo "ui-screenshot: FAILED" >&2
  exit 1
fi
echo "ui-screenshot: OK ($i scenes, output in $OUT)"
