#!/usr/bin/env bash
# Headless Ubuntu cloud guest smoke test for environments without /dev/kvm
# (Cursor Cloud agents, nested Docker). Uses QEMU TCG + cloud-init + 9p share.
#
# For a real Mint Cinnamon rice lab with Virt-Manager, use create-mint-guest.sh
# on a host that has KVM (see docs/vm-lab.md).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

REPO_ROOT="$(vm_repo_root)"
WORK_DIR="${LMDESKTOPPLUS_SMOKE_DIR:-$REPO_ROOT/.vm-lab}"
IMAGE_URL="${LMDESKTOPPLUS_CLOUD_IMAGE_URL:-https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img}"
IMAGE_NAME="ubuntu-24.04-cloud.img"
SSH_PORT="${LMDESKTOPPLUS_SMOKE_SSH_PORT:-2222}"
RAM_MIB="${LMDESKTOPPLUS_SMOKE_RAM_MIB:-2048}"
KEEP=0
DOWNLOAD_ONLY=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Boot an Ubuntu 24.04 cloud image under QEMU, share the repo via 9p, and run
./tests/run-all.sh inside the guest.

Options:
  --work-dir DIR   Image/seed directory (default: .vm-lab/)
  --ssh-port N     Host port forwarded to guest :22 (default: ${SSH_PORT})
  --ram MIB        Guest RAM (default: ${RAM_MIB})
  --keep           Leave QEMU running after tests
  --download-only  Fetch cloud image and exit
  -h, --help       Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --ssh-port) SSH_PORT="$2"; shift 2 ;;
    --ram) RAM_MIB="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --download-only) DOWNLOAD_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      vm_log_err "unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

vm_require_cmd qemu-system-x86_64 qemu-img cloud-localds curl sshpass ssh || exit 1

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

if [[ ! -f "$IMAGE_NAME" ]]; then
  vm_log_info "downloading cloud image → ${WORK_DIR}/${IMAGE_NAME}"
  curl -L --fail --retry 3 -o "$IMAGE_NAME" "$IMAGE_URL"
fi

if [[ "$DOWNLOAD_ONLY" -eq 1 ]]; then
  vm_log_info "download-only complete"
  exit 0
fi

if [[ -e /dev/kvm ]]; then
  ACCEL=(-enable-kvm -cpu host)
  vm_log_info "using KVM acceleration"
else
  ACCEL=(-accel tcg,thread=multi -cpu max)
  vm_log_warn "no /dev/kvm — using TCG (slow). Mint GUI lab needs host KVM."
fi

qemu-img create -f qcow2 -F qcow2 -b "$IMAGE_NAME" lmdp-smoke.qcow2 20G >/dev/null

cat > user-data <<EOF
#cloud-config
hostname: lmdp-smoke
manage_etc_hosts: true
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    plain_text_passwd: "ubuntu"
ssh_pwauth: true
package_update: false
runcmd:
  - |
    set -eux
    export HOME=/home/ubuntu
    mkdir -p /mnt/lmdesktopplus /home/ubuntu/tmp
    chown ubuntu:ubuntu /home/ubuntu/tmp
    for i in \$(seq 1 60); do
      if mount -t 9p -o trans=virtio,version=9p2000.L lmdesktopplus /mnt/lmdesktopplus; then
        break
      fi
      sleep 1
    done
    cd /mnt/lmdesktopplus
    export PYTHONPATH=src HOME=/home/ubuntu TMPDIR=/home/ubuntu/tmp
    if ./tests/run-all.sh > /var/tmp/lmdp-tests.log 2>&1; then
      echo OK > /var/tmp/lmdp-tests.status
    else
      echo FAIL > /var/tmp/lmdp-tests.status
    fi
    sync
    echo done > /var/tmp/lmdp-boot.done
    echo "===== LMDP TEST \$(cat /var/tmp/lmdp-tests.status) ====="
EOF

cat > meta-data <<'EOF'
instance-id: lmdp-smoke-001
local-hostname: lmdp-smoke
EOF

cloud-localds seed.iso user-data meta-data

vm_log_info "starting qemu (ssh → 127.0.0.1:${SSH_PORT})"
qemu-system-x86_64 \
  -machine q35 \
  -m "$RAM_MIB" \
  -smp 2 \
  "${ACCEL[@]}" \
  -drive "file=lmdp-smoke.qcow2,if=virtio,format=qcow2" \
  -drive "file=seed.iso,if=virtio,format=raw,media=cdrom" \
  -netdev "user,id=net0,hostfwd=tcp::${SSH_PORT}-:22" \
  -device virtio-net-pci,netdev=net0 \
  -virtfs "local,path=${REPO_ROOT},mount_tag=lmdesktopplus,security_model=mapped-xattr,id=repo" \
  -display none \
  -daemonize \
  -pidfile qemu.pid \
  -serial "file:qemu.serial.log"

cleanup() {
  if [[ "$KEEP" -eq 1 ]]; then
    vm_log_info "leaving qemu running (pid $(cat qemu.pid 2>/dev/null || echo '?'))"
    return 0
  fi
  if [[ -f qemu.pid ]]; then
    kill "$(cat qemu.pid)" 2>/dev/null || true
    rm -f qemu.pid
  fi
}
trap cleanup EXIT

vm_log_info "waiting for ssh…"
for _ in $(seq 1 90); do
  if sshpass -p ubuntu ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=2 \
    -p "$SSH_PORT" ubuntu@127.0.0.1 'true' 2>/dev/null; then
    break
  fi
  sleep 2
done

vm_log_info "waiting for cloud-init test run…"
STATUS=""
for _ in $(seq 1 120); do
  STATUS="$(
    sshpass -p ubuntu ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=2 \
      -p "$SSH_PORT" ubuntu@127.0.0.1 \
      'cat /var/tmp/lmdp-tests.status 2>/dev/null || true' 2>/dev/null || true
  )"
  if [[ "$STATUS" == "OK" || "$STATUS" == "FAIL" ]]; then
    break
  fi
  sleep 3
done

sshpass -p ubuntu ssh \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -p "$SSH_PORT" ubuntu@127.0.0.1 \
  'tail -n 60 /var/tmp/lmdp-tests.log 2>/dev/null || true' || true

if [[ "$STATUS" != "OK" ]]; then
  vm_log_err "guest tests failed (status=${STATUS:-unknown})"
  exit 1
fi

vm_log_info "guest tests OK"
