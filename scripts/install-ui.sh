#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"
APP_ROOT="$HOME/.local/share/lmdesktopplus/app"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
PACKAGE_WALLPAPER_DIR="$HOME/.local/share/lmdesktopplus/assets/wallpapers"

log(){ printf '==> %s\n' "$*" >&2; }
run(){ if [[ "$DRY_RUN" == "1" ]]; then log "[dry-run] $*"; else "$@"; fi; }

if [[ "$DRY_RUN" == "1" ]]; then
  log "[dry-run] would install Python package -> $APP_ROOT/lmdesktopplus"
  log "[dry-run] would install launcher -> $BIN_DIR/lmdesktopplus"
  log "[dry-run] would install desktop entry and icon"
  exit 0
fi

mkdir -p "$APP_ROOT" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$PACKAGE_WALLPAPER_DIR/thumbs"
rm -rf "$APP_ROOT/lmdesktopplus"
cp -a "$ROOT/src/lmdesktopplus" "$APP_ROOT/lmdesktopplus"
cp -a "$ROOT/assets/wallpapers/vapor-matrix.svg" "$PACKAGE_WALLPAPER_DIR/vapor-matrix.svg"
cp -a "$ROOT/assets/wallpapers/thumbs/." "$PACKAGE_WALLPAPER_DIR/thumbs/"
find "$APP_ROOT/lmdesktopplus" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$APP_ROOT/lmdesktopplus" -type f -name '*.py[co]' -delete
cat > "$BIN_DIR/lmdesktopplus" <<WRAPPER
#!/usr/bin/env sh
PYTHONPATH="$APP_ROOT" exec python3 -m lmdesktopplus "\$@"
WRAPPER
chmod 0755 "$BIN_DIR/lmdesktopplus"

sed "s#^Exec=.*#Exec=$BIN_DIR/lmdesktopplus#; s#^TryExec=.*#TryExec=$BIN_DIR/lmdesktopplus#" \
  "$ROOT/share/applications/lmdesktopplus.desktop" > "$DESKTOP_DIR/lmdesktopplus.desktop"
cp -a "$ROOT/share/icons/hicolor/scalable/apps/lmdesktopplus.svg" "$ICON_DIR/lmdesktopplus.svg"

# Create initial settings and generated GTK/Hyprland overlays.
PYTHONPATH="$APP_ROOT" python3 - <<'PY'
from lmdesktopplus.config import SettingsStore
from lmdesktopplus.agents import AgentRegistry
from lmdesktopplus.theme import apply
settings = SettingsStore().get()
AgentRegistry()
apply(settings)
PY

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi
log "Installed LMDesktopPlus UI. Launch with: $BIN_DIR/lmdesktopplus"
