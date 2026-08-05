#!/usr/bin/env bash
# Run inside the smoke guest (or any Ubuntu host with the repo mounted).
# Executes the full suite, then applies user-local UI + Debian package.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
SKIP_APPLY="${SKIP_APPLY:-0}"
export HOME="${HOME:-/home/ubuntu}"
export TMPDIR="${TMPDIR:-$HOME/tmp}"
mkdir -p "$TMPDIR"

# Cloud-init / root probes can leave root-owned XDG dirs; reclaim for the user.
if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
  TARGET_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
  chown -R "$SUDO_USER:$SUDO_USER" "$TARGET_HOME/.local" "$TARGET_HOME/.config" 2>/dev/null || true
fi
if [[ -d "$HOME/.local" && ! -w "$HOME/.local" ]]; then
  echo "HOME .local not writable; fix ownership first" >&2
  ls -la "$HOME" "$HOME/.local" >&2 || true
  exit 1
fi

git config --global --add safe.directory "$ROOT" 2>/dev/null || true

echo "===== LMDP guest apply start ====="
uname -a
python3 --version

./tests/run-all.sh

if [[ "$SKIP_APPLY" -eq 1 ]]; then
  echo "===== skip apply ====="
  exit 0
fi

echo "===== apply user-local UI ====="
./scripts/install-ui.sh
export PATH="$HOME/.local/bin:$PATH"
lmdesktopplus --help >/tmp/lmdp-help.txt || true
VERSION="$(PYTHONPATH="$HOME/.local/share/lmdesktopplus/app" python3 -c 'import lmdesktopplus; print(lmdesktopplus.__version__)')"
echo "installed UI version=$VERSION"
echo "$VERSION" | tee /var/tmp/lmdp-ui-version.txt >/dev/null || echo "$VERSION" > "$HOME/lmdp-ui-version.txt"

echo "===== apply Debian package ====="
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"
DEB="dist/lmdesktopplus_${VERSION}_all.deb"
if [[ ! -f "$DEB" ]]; then
  # 9p share may leave root-owned build/ from an earlier cloud-init root run.
  rm -rf build/deb 2>/dev/null || sudo rm -rf build/deb
  DEB="$(./packaging/build-deb.sh | tail -n1)"
fi
echo "deb=$DEB"
if [[ "$(id -u)" -eq 0 ]]; then
  apt-get install -y dpkg-dev xz-utils
  apt-get install -y "$DEB"
else
  sudo apt-get install -y dpkg-dev xz-utils
  sudo apt-get install -y "$DEB"
fi
/usr/bin/lmdesktopplus --help >/tmp/lmdp-deb-help.txt || true
dpkg-query -W -f='${Package} ${Version}\n' lmdesktopplus | tee /var/tmp/lmdp-deb-version.txt || true
ls -la dist/*.deb dist/*-freebsd.txz 2>/dev/null || true

echo "===== LMDP guest apply OK ====="
