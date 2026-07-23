#!/usr/bin/env bash
# Prove Hyprland installer flags never silently add a community PPA.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

run_dry() {
  DRY_RUN=1 bash "$ROOT/scripts/install-hyprland-mint.sh" "$@" 2>&1
}

out="$(run_dry)"
if printf '%s\n' "$out" | grep -q 'add-apt-repository'; then
  echo "FAIL: distro-only dry-run mentioned add-apt-repository"
  fail=1
else
  echo "OK: distro-only dry-run does not add PPA"
fi
if ! printf '%s\n' "$out" | grep -q 'community PPA would NOT be added'; then
  echo "FAIL: distro-only dry-run missing explicit no-PPA message"
  fail=1
else
  echo "OK: distro-only dry-run states community PPA would NOT be added"
fi

out_ppa="$(run_dry --allow-community-ppa)"
if ! printf '%s\n' "$out_ppa" | grep -q 'add-apt-repository -y ppa:cppiber/hyprland'; then
  echo "FAIL: --allow-community-ppa dry-run did not plan PPA add"
  fail=1
else
  echo "OK: --allow-community-ppa dry-run plans PPA add"
fi

out_src="$(run_dry --hyprland-source=ppa)"
if ! printf '%s\n' "$out_src" | grep -q 'add-apt-repository -y ppa:cppiber/hyprland'; then
  echo "FAIL: --hyprland-source=ppa dry-run did not plan PPA add"
  fail=1
else
  echo "OK: --hyprland-source=ppa dry-run plans PPA add"
fi

# install.sh flag plumbing
if ! ./install.sh --help 2>&1 | grep -q -- '--allow-community-ppa'; then
  echo "FAIL: install.sh --help missing --allow-community-ppa"
  fail=1
else
  echo "OK: install.sh documents --allow-community-ppa"
fi

help_out="$(./install.sh --dry-run --with-hyprland 2>&1 || true)"
if printf '%s\n' "$help_out" | grep -q 'add-apt-repository'; then
  echo "FAIL: install.sh --with-hyprland dry-run planned community PPA without opt-in"
  fail=1
else
  echo "OK: install.sh --with-hyprland dry-run stays distro-only"
fi

# No swallowed apt redirection in installer script
if grep -nE 'apt-get install .*2>/dev/null' "$ROOT/scripts/install-hyprland-mint.sh"; then
  echo "FAIL: install-hyprland-mint.sh still suppresses apt stderr"
  fail=1
else
  echo "OK: apt install errors are not redirected to /dev/null"
fi

# TTY launcher writes to state log path (string presence)
if ! grep -q 'hyprland-start.log' "$ROOT/scripts/start-hyprland-tty.sh"; then
  echo "FAIL: start-hyprland-tty.sh missing startup log path"
  fail=1
else
  echo "OK: start-hyprland-tty.sh records startup log"
fi

# One-shot arm must be consumed by bashrc (prefer hardened launcher).
if ! grep -q 'start-hyprland-once' "$ROOT/packages/shared/bash/bashrc.snippet"; then
  echo "FAIL: bashrc.snippet does not consume start-hyprland-once"
  fail=1
else
  echo "OK: bashrc.snippet consumes start-hyprland-once"
fi
if ! grep -q 'bin/start-hyprland-tty.sh' "$ROOT/packages/shared/bash/bashrc.snippet"; then
  echo "FAIL: bashrc.snippet does not prefer hardened TTY launcher"
  fail=1
else
  echo "OK: bashrc.snippet prefers hardened TTY launcher"
fi

# Fresh installs must stub the generated overlay that hyprland.conf sources.
if ! grep -q 'hypr-generated.conf' "$ROOT/install.sh"; then
  echo "FAIL: install.sh does not ensure hypr-generated.conf stub"
  fail=1
else
  echo "OK: install.sh ensures hypr-generated.conf stub"
fi
if ! grep -q 'source = ~/.config/lmdesktopplus/hypr-generated.conf' \
  "$ROOT/packages/hyprland/hypr/hyprland.conf"; then
  echo "FAIL: hyprland.conf missing generated overlay source"
  fail=1
else
  echo "OK: hyprland.conf sources generated overlay path"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "hyprland-install-flags OK"
