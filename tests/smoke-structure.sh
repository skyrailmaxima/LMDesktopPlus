#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
need() { [[ -e "$ROOT/$1" ]] || { echo "MISSING: $1"; fail=1; }; }
need "palette/vapor-matrix.theme"
need "install.sh"
need "uninstall.sh"
need "lib/common.sh"
need "packages/shared/kitty/kitty.conf"
need "packages/hyprland/hypr/hyprland.conf"
need "packages/cinnamon/README.md"
if [[ "$fail" -ne 0 ]]; then exit 1; fi
echo "structure OK"
