#!/usr/bin/env bash
# Ensure virtiofs share is attached to an existing lab guest; print mount help.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

NAME="$DEFAULT_NAME"
REPO_PATH="$(vm_repo_root)"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Attach (or verify) virtiofs share of the host repo on a lab guest.

Options:
  --name NAME         Domain name (default: ${DEFAULT_NAME})
  --repo-path PATH    Host path to share (default: repo root)
  --dry-run           Print planned actions; change nothing
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --repo-path) REPO_PATH="$2"; shift 2 ;;
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

if [[ ! -d "$REPO_PATH" ]]; then
  vm_log_err "repo path not a directory: $REPO_PATH"
  exit 1
fi

XML="$(cat <<EOF
<filesystem type='mount' accessmode='passthrough'>
  <driver type='virtiofs'/>
  <source dir='${REPO_PATH}'/>
  <target dir='${VIRTIOFS_TAG}'/>
</filesystem>
EOF
)"

vm_log_info "domain=${NAME}"
vm_log_info "share ${REPO_PATH} -> tag ${VIRTIOFS_TAG}"

if [[ "$DRY_RUN" == "1" ]]; then
  vm_log_info "dry-run: would ensure shared memory backing + attach filesystem device"
  printf '%s\n' "$XML"
  print_guest_mount_help
  exit 0
fi

vm_require_cmd virsh || exit 1

if ! virsh dominfo "$NAME" >/dev/null 2>&1; then
  vm_log_err "domain '${NAME}' not found — create it first with create-mint-guest.sh"
  exit 1
fi

if virsh dumpxml "$NAME" 2>/dev/null | grep -q "<target dir='${VIRTIOFS_TAG}'/>"; then
  vm_log_info "virtiofs tag '${VIRTIOFS_TAG}' already present on ${NAME}"
else
  TMPXML="$(mktemp)"
  printf '%s\n' "$XML" >"$TMPXML"
  if virsh domstate "$NAME" 2>/dev/null | grep -qi running; then
    vm_log_info "attaching filesystem (live + config)…"
    virsh attach-device "$NAME" "$TMPXML" --live --config || {
      vm_log_warn "live attach failed; trying --config only (reboot guest to pick up share)"
      virsh attach-device "$NAME" "$TMPXML" --config
    }
  else
    vm_log_info "attaching filesystem (config; start guest to use share)…"
    virsh attach-device "$NAME" "$TMPXML" --config
  fi
  rm -f "$TMPXML"
fi

vm_log_info "guest mount instructions:"
print_guest_mount_help
