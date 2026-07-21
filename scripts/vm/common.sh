#!/usr/bin/env bash
# Shared helpers for LMDesktopPlus VM lab scripts.
# shellcheck shell=bash

LAB_PREFIX="${LAB_PREFIX:-lmdesktopplus-}"
DEFAULT_NAME="${DEFAULT_NAME:-lmdesktopplus-mint}"
VIRTIOFS_TAG="${VIRTIOFS_TAG:-lmdesktopplus}"
GUEST_MOUNT="${GUEST_MOUNT:-/mnt/lmdesktopplus}"
DEFAULT_RAM_MIB="${DEFAULT_RAM_MIB:-8192}"
DEFAULT_VCPUS="${DEFAULT_VCPUS:-4}"
DEFAULT_DISK_GB="${DEFAULT_DISK_GB:-40}"

vm_log_info() { printf '==> %s\n' "$*" >&2; }
vm_log_warn() { printf '!!  %s\n' "$*" >&2; }
vm_log_err()  { printf 'xx  %s\n' "$*" >&2; }

vm_repo_root() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$here"
}

vm_require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || {
      vm_log_err "missing required command: $c (see docs/vm-lab.md)"
      return 1
    }
  done
}

assert_lab_name() {
  local name="$1"
  if [[ "$name" != "$LAB_PREFIX"* ]]; then
    vm_log_err "refusing non-lab domain '$name' (must start with ${LAB_PREFIX})"
    return 1
  fi
}

vm_cap_vcpus() {
  local want="$1"
  local host max
  host="$(nproc 2>/dev/null || echo 2)"
  if (( host > 1 )); then
    max=$((host - 1))
  else
    max=1
  fi
  if (( want > max )); then
    printf '%s\n' "$max"
  else
    printf '%s\n' "$want"
  fi
}

print_guest_mount_help() {
  local tag="${1:-$VIRTIOFS_TAG}"
  local mnt="${2:-$GUEST_MOUNT}"
  cat <<EOF
# Inside the Mint guest (after first boot / install):

sudo mkdir -p ${mnt}
sudo mount -t virtiofs ${tag} ${mnt}

# Optional persistent mount — add to /etc/fstab:
# ${tag} ${mnt} virtiofs defaults 0 0

# Then install from the share:
cd ${mnt}
./install.sh

# Optional clean git clone (dual sync):
# mkdir -p ~/src && git clone https://github.com/skyrailmaxima/LMDesktopPlus.git ~/src/LMDesktopPlus
EOF
}
