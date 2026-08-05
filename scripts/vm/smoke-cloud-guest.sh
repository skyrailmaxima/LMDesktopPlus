#!/usr/bin/env bash
# Headless Ubuntu cloud guest smoke test for environments without /dev/kvm
# (Cursor Cloud agents, nested Docker). Uses QEMU TCG + cloud-init + 9p share.
#
# Runs ./tests/run-all.sh, then applies the machine UI build via install-ui.sh
# and a local .deb install so the guest exercises the packaged entrypoint.
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
RAM_MIB="${LMDESKTOPPLUS_SMOKE_RAM_MIB:-3072}"
KEEP=0
DOWNLOAD_ONLY=0
SKIP_APPLY=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Boot an Ubuntu 24.04 cloud image under QEMU, share the repo via 9p, run
./tests/run-all.sh, then apply the UI build (install-ui.sh + local .deb).

Options:
  --work-dir DIR   Image/seed directory (default: .vm-lab/)
  --ssh-port N     Host port forwarded to guest :22 (default: ${SSH_PORT})
  --ram MIB        Guest RAM (default: ${RAM_MIB})
  --keep           Leave QEMU running after tests
  --skip-apply     Only run ./tests/run-all.sh (no install-ui / deb apply)
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
    --skip-apply) SKIP_APPLY=1; shift ;;
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

rm -f lmdp-smoke.qcow2 seed.iso qemu.pid qemu.serial.log
qemu-img create -f qcow2 -F qcow2 -b "$IMAGE_NAME" lmdp-smoke.qcow2 20G >/dev/null

# Cloud-init mounts the repo and runs guest-apply-build.sh (bash, not dash).
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
package_update: true
package_upgrade: false
runcmd:
  - [/bin/bash, -lc, 'mkdir -p /mnt/lmdesktopplus /home/ubuntu/tmp && chown ubuntu:ubuntu /home/ubuntu/tmp && for i in $(seq 1 90); do mount -t 9p -o trans=virtio,version=9p2000.L lmdesktopplus /mnt/lmdesktopplus && break; sleep 1; done && test -d /mnt/lmdesktopplus/scripts/vm && chown -R ubuntu:ubuntu /home/ubuntu/.local /home/ubuntu/.config 2>/dev/null || true && STATUS=OK && sudo -u ubuntu -H env HOME=/home/ubuntu TMPDIR=/home/ubuntu/tmp SKIP_APPLY=${SKIP_APPLY} /bin/bash /mnt/lmdesktopplus/scripts/vm/guest-apply-build.sh >/var/tmp/lmdp-tests.log 2>&1 || STATUS=FAIL; echo \$STATUS >/var/tmp/lmdp-tests.status; sync; echo done >/var/tmp/lmdp-boot.done; echo ===== LMDP TEST \$STATUS =====']
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
for _ in $(seq 1 180); do
  if sshpass -p ubuntu ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=2 \
    -p "$SSH_PORT" ubuntu@127.0.0.1 'true' 2>/dev/null; then
    break
  fi
  sleep 2
done

if ! sshpass -p ubuntu ssh \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=2 \
  -p "$SSH_PORT" ubuntu@127.0.0.1 'true' 2>/dev/null; then
  vm_log_err "ssh never became ready; last serial lines:"
  tail -n 80 qemu.serial.log 2>/dev/null || true
  exit 1
fi

vm_log_info "waiting for guest apply (tests + install)…"
STATUS=""
for _ in $(seq 1 400); do
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
  sleep 5
done

sshpass -p ubuntu ssh \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -p "$SSH_PORT" ubuntu@127.0.0.1 \
  'tail -n 80 /var/tmp/lmdp-tests.log 2>/dev/null; echo ---; cat /var/tmp/lmdp-ui-version.txt /var/tmp/lmdp-deb-version.txt 2>/dev/null || true' || true

if [[ "$STATUS" != "OK" ]]; then
  vm_log_err "guest apply failed (status=${STATUS:-unknown})"
  exit 1
fi

vm_log_info "guest tests + build apply OK"
if [[ "$KEEP" -eq 1 ]]; then
  vm_log_info "ssh: sshpass -p ubuntu ssh -p ${SSH_PORT} ubuntu@127.0.0.1"
fi
