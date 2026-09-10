#!/usr/bin/env bash
# Dry-run / gate tests for VM lab scripts (no libvirt required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CREATE="$ROOT/scripts/vm/create-mint-guest.sh"
ATTACH="$ROOT/scripts/vm/attach-share.sh"
DESTROY="$ROOT/scripts/vm/destroy-mint-guest.sh"
fail=0

pass() { printf 'OK  %s\n' "$*"; }
bad()  { printf 'FAIL %s\n' "$*"; fail=1; }

FAKE_ISO="$(mktemp --suffix=.iso)"
trap 'rm -f "$FAKE_ISO"' EXIT
: >"$FAKE_ISO"

# create: dry-run succeeds
if out="$("$CREATE" --iso "$FAKE_ISO" --dry-run 2>&1)"; then
  echo "$out" | grep -q virt-install && pass "create dry-run prints virt-install" || bad "create dry-run missing virt-install"
else
  bad "create dry-run exited non-zero"
fi

# create: refuses non-lab name
if "$CREATE" --name evil-vm --iso "$FAKE_ISO" --dry-run >/dev/null 2>&1; then
  bad "create should refuse non-lab name"
else
  pass "create refuses non-lab name"
fi

# create: --autostart-ui prints the true-UI recipe
if out="$("$CREATE" --iso "$FAKE_ISO" --autostart-ui --dry-run 2>&1)"; then
  echo "$out" | grep -q 'install-ui.sh --autostart-ui' && pass "create --autostart-ui prints true-UI recipe" || bad "create --autostart-ui missing true-UI recipe"
else
  bad "create --autostart-ui dry-run exited non-zero"
fi

# install-ui: --autostart-ui dry-run mentions login autostart
INSTALL_UI="$ROOT/scripts/install-ui.sh"
if out="$("$INSTALL_UI" --autostart-ui --dry-run 2>&1)"; then
  echo "$out" | grep -qi 'autostart' && pass "install-ui --autostart-ui dry-run mentions autostart" || bad "install-ui --autostart-ui missing autostart note"
else
  bad "install-ui --autostart-ui dry-run exited non-zero"
fi

# create: missing iso
if "$CREATE" --dry-run >/dev/null 2>&1; then
  bad "create should require iso"
else
  pass "create requires iso"
fi

# attach: dry-run
if "$ATTACH" --dry-run >/dev/null 2>&1; then
  pass "attach dry-run"
else
  bad "attach dry-run failed"
fi

# destroy: requires --force
if "$DESTROY" --name lmdesktopplus-mint --dry-run >/dev/null 2>&1; then
  bad "destroy should require --force"
else
  pass "destroy requires --force"
fi

# destroy: refuses non-lab even with --force
if "$DESTROY" --name other-vm --force --dry-run >/dev/null 2>&1; then
  bad "destroy should refuse non-lab name"
else
  pass "destroy refuses non-lab name"
fi

# destroy: dry-run with force
if "$DESTROY" --name lmdesktopplus-mint --force --dry-run >/dev/null 2>&1; then
  pass "destroy dry-run with --force"
else
  bad "destroy dry-run with --force failed"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "test-vm-scripts: FAILED"
  exit 1
fi
echo "test-vm-scripts: OK"
