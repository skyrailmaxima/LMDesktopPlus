#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/common.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME"
export BACKUP_ROOT="$TMP/backup"
mkdir -p "$HOME/.config/kitty"
echo old > "$HOME/.config/kitty/kitty.conf"
mkdir -p "$TMP/pkg"
echo new > "$TMP/pkg/kitty.conf"
link_file "$TMP/pkg/kitty.conf" "$HOME/.config/kitty/kitty.conf"
[[ -L "$HOME/.config/kitty/kitty.conf" ]]
[[ -f "$BACKUP_ROOT"/*/.config/kitty/kitty.conf ]] || [[ -f $(find "$BACKUP_ROOT" -name kitty.conf | head -1) ]]
echo "common OK"
