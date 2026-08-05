#!/usr/bin/env bash
# Task 23: smoke-check optional GNU stow frontend + Suggests map.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

test -x ./stow.sh
test -f ./docs/suggests.md
grep -q 'mpvpaper' ./docs/suggests.md
grep -q 'Suggests:' ./packaging/build-deb.sh

./stow.sh --help >/tmp/lmdesktopplus-stow-help.txt
grep -q 'materialize-only' /tmp/lmdesktopplus-stow-help.txt

rm -rf packaging/.stow-build
./stow.sh --materialize-only --with-hyprland
test -L packaging/.stow-build/shared/.config/kitty/kitty.conf
test -L packaging/.stow-build/hyprland/.config/hypr/hyprland.conf
test -L packaging/.stow-build/shared/.config/vapor-matrix.theme

if command -v stow >/dev/null 2>&1; then
  TARGET="$(mktemp -d /tmp/lmdesktopplus-stow-target.XXXXXX)"
  ./stow.sh --dry-run --target "$TARGET"
  rm -rf "$TARGET"
else
  set +e
  ./stow.sh >/tmp/lmdesktopplus-stow-missing.txt 2>&1
  code=$?
  set -e
  [[ "$code" -eq 2 ]]
  grep -q 'install.sh' /tmp/lmdesktopplus-stow-missing.txt
fi

printf 'stow-mode OK\n'
