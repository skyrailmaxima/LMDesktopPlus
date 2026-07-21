#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
need() { [[ -e "$ROOT/$1" ]] || { echo "MISSING: $1"; fail=1; }; }
need "palette/vapor-matrix.theme"
need "install.sh"
need "uninstall.sh"
need "lib/common.sh"
need "lib/detect.sh"
need "packages/shared/kitty/kitty.conf"
need "packages/hyprland/hypr/hyprland.conf"
need "packages/cinnamon/README.md"
need "pyproject.toml"
need "src/lmdesktopplus/main.py"
need "src/lmdesktopplus/server.py"
need "src/lmdesktopplus/static/index.html"
need "src/lmdesktopplus/static/app.js"
need "src/lmdesktopplus/static/digitalvapor.css"
need "src/lmdesktopplus/static/digitalvapor.js"
need "docs/digitalvapor-design-system.md"
need "scripts/install-ui.sh"
need "packaging/build-deb.sh"
if [[ "$fail" -ne 0 ]]; then exit 1; fi
echo "structure OK"
