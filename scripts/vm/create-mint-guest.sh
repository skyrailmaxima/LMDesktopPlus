#!/usr/bin/env bash
# Create a disposable Linux Mint lab guest for LMDesktopPlus iteration.
# Uses virt-install; finish the OS install in Virt-Manager.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

NAME="$DEFAULT_NAME"
ISO="${MINT_ISO:-}"
RAM_MIB="$DEFAULT_RAM_MIB"
VCPUS="$DEFAULT_VCPUS"
DISK_GB="$DEFAULT_DISK_GB"
REPO_PATH="$(vm_repo_root)"
DRY_RUN="${DRY_RUN:-0}"
AUTOSTART_UI="${AUTOSTART_UI:-0}"
DISK_DIR="${LMDESKTOPPLUS_VM_DISK_DIR:-$HOME/VirtualMachines}"

usage() {
  cat <<EOF
Usage: $(basename "$0") --iso /path/to/linuxmint.iso [options]

Create a QEMU/KVM lab guest (prefix ${LAB_PREFIX}*) with virtiofs share of the repo.

Options:
  --name NAME         Domain name (default: ${DEFAULT_NAME})
  --iso PATH          Linux Mint Cinnamon ISO (or set MINT_ISO)
  --ram MIB           RAM in MiB (default: ${DEFAULT_RAM_MIB})
  --vcpus N           vCPUs (default: ${DEFAULT_VCPUS}; capped to nproc-1)
  --disk-gb N         Disk size in GiB (default: ${DEFAULT_DISK_GB})
  --repo-path PATH    Host path shared via virtiofs (default: repo root)
  --disk-dir PATH     Directory for qcow2 (default: ~/VirtualMachines)
  --autostart-ui      Also print the true-UI install + login-autostart recipe
  --dry-run           Print virt-install plan; change nothing
  -h, --help          Show this help

See docs/vm-lab.md for host packages, Virt-Manager install, and lab mode.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --iso) ISO="$2"; shift 2 ;;
    --ram) RAM_MIB="$2"; shift 2 ;;
    --vcpus) VCPUS="$2"; shift 2 ;;
    --disk-gb) DISK_GB="$2"; shift 2 ;;
    --repo-path) REPO_PATH="$2"; shift 2 ;;
    --disk-dir) DISK_DIR="$2"; shift 2 ;;
    --autostart-ui) AUTOSTART_UI=1; shift ;;
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

if [[ -z "$ISO" ]]; then
  vm_log_err "ISO required: pass --iso or set MINT_ISO"
  exit 1
fi
if [[ ! -f "$ISO" ]]; then
  vm_log_err "ISO not found: $ISO"
  exit 1
fi
if [[ ! -d "$REPO_PATH" ]]; then
  vm_log_err "repo path not a directory: $REPO_PATH"
  exit 1
fi

VCPUS="$(vm_cap_vcpus "$VCPUS")"
DISK_PATH="${DISK_DIR}/${NAME}.qcow2"

vm_log_info "name=${NAME}"
vm_log_info "iso=${ISO}"
vm_log_info "ram_mib=${RAM_MIB} vcpus=${VCPUS} disk_gb=${DISK_GB}"
vm_log_info "disk=${DISK_PATH}"
vm_log_info "virtiofs ${REPO_PATH} -> tag ${VIRTIOFS_TAG}"

CMD=(
  virt-install
  --name "$NAME"
  --memory "$RAM_MIB"
  --vcpus "$VCPUS"
  --cpu host
  --disk "path=${DISK_PATH},size=${DISK_GB},bus=virtio,format=qcow2"
  --cdrom "$ISO"
  --os-variant detect=on,name=linuxmint22
  --network network=default,model=virtio
  --graphics spice,listen=none
  --video virtio
  --channel spicevmc
  --boot uefi
  --memorybacking source.type=memfd,access.mode=shared
  --filesystem "type=mount,accessmode=passthrough,driver.type=virtiofs,source.dir=${REPO_PATH},target.dir=${VIRTIOFS_TAG}"
  --noautoconsole
)

if [[ "$DRY_RUN" == "1" ]]; then
  vm_log_info "dry-run: would ensure disk dir ${DISK_DIR}"
  vm_log_info "dry-run: would run:"
  printf '  %q' "${CMD[@]}"
  printf '\n'
  vm_log_info "after create: open Virt-Manager, finish Mint install, then mount share:"
  print_guest_mount_help
  if [[ "$AUTOSTART_UI" == "1" ]]; then
    vm_log_info "then iterate the true UI:"
    print_true_ui_help
  fi
  exit 0
fi

vm_require_cmd virt-install virsh || exit 1

if virsh dominfo "$NAME" >/dev/null 2>&1; then
  vm_log_err "domain '${NAME}' already exists — destroy first:"
  vm_log_err "  ./scripts/vm/destroy-mint-guest.sh --name ${NAME} --force"
  exit 1
fi

mkdir -p "$DISK_DIR"
vm_log_info "running virt-install (console: Virt-Manager)…"
"${CMD[@]}"
vm_log_info "domain created. Complete Linux Mint install in Virt-Manager, then:"
print_guest_mount_help
if [[ "$AUTOSTART_UI" == "1" ]]; then
  vm_log_info "then iterate the true UI:"
  print_true_ui_help
fi
