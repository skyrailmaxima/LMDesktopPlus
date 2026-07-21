#!/usr/bin/env bash
# Destroy a disposable LMDesktopPlus lab guest (name prefix gated).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

NAME="$DEFAULT_NAME"
FORCE=0
DRY_RUN="${DRY_RUN:-0}"
DISK_DIR="${LMDESKTOPPLUS_VM_DISK_DIR:-$HOME/VirtualMachines}"

usage() {
  cat <<EOF
Usage: $(basename "$0") --name ${DEFAULT_NAME} --force [options]

Destroy a lab guest domain and its disk. Refuses names outside ${LAB_PREFIX}*.

Options:
  --name NAME         Domain name (default: ${DEFAULT_NAME})
  --force             Required — confirm destructive action
  --disk-dir PATH     Where qcow2 was created (default: ~/VirtualMachines)
  --dry-run           Print planned actions; change nothing
  -h, --help          Show this help

Lab mode: guests are disposable. Prefer snapshots for undo when possible;
use this when you want a full rebuild from ISO.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --disk-dir) DISK_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      vm_log_err "unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

assert_lab_name "$NAME" || exit 1

if [[ "$FORCE" != "1" ]]; then
  vm_log_err "refusing to destroy without --force"
  exit 1
fi

DISK_PATH="${DISK_DIR}/${NAME}.qcow2"

vm_log_info "will destroy domain=${NAME} disk=${DISK_PATH}"

if [[ "$DRY_RUN" == "1" ]]; then
  vm_log_info "dry-run: virsh destroy ${NAME} (if running)"
  vm_log_info "dry-run: virsh undefine ${NAME} --nvram (UEFI)"
  vm_log_info "dry-run: remove ${DISK_PATH} if present"
  exit 0
fi

vm_require_cmd virsh || exit 1

if virsh dominfo "$NAME" >/dev/null 2>&1; then
  if virsh domstate "$NAME" 2>/dev/null | grep -qi running; then
    vm_log_info "destroying running domain ${NAME}…"
    virsh destroy "$NAME" || true
  fi
  vm_log_info "undefining ${NAME}…"
  if ! virsh undefine "$NAME" --nvram 2>/dev/null; then
    virsh undefine "$NAME" || true
  fi
else
  vm_log_warn "domain '${NAME}' not registered in libvirt"
fi

if [[ -f "$DISK_PATH" ]]; then
  vm_log_info "removing disk ${DISK_PATH}"
  rm -f "$DISK_PATH"
else
  vm_log_warn "disk not found at ${DISK_PATH} (already removed or different --disk-dir)"
fi

vm_log_info "done — recreate with scripts/vm/create-mint-guest.sh"
