# LMDesktopPlus VM Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scripted QEMU/KVM Mint lab (`scripts/vm/`) so LMDesktopPlus can be installed and iterated inside a disposable Linux Mint guest with virtiofs + git sync.

**Architecture:** Host scripts wrap `virt-install`/`virsh` to create, attach shares to, and destroy domains named `lmdesktopplus-*`. Guest mounts the host repo at `/mnt/lmdesktopplus` and may also git-clone the remote. Lab mode favors snapshots and `--force` destroy/recreate over protecting guest state.

**Tech Stack:** Bash, `virt-install`, `virsh`, libvirt, Virt-Manager, virtiofs, Linux Mint Cinnamon ISO.

## Global Constraints

- Lab domain names must match prefix `lmdesktopplus-` (default name `lmdesktopplus-mint`).
- Destroy/recreate requires `--force` and the name prefix gate.
- `--dry-run` prints planned actions and must not call `virt-install`/`virsh` mutators.
- Virtiofs tag: `lmdesktopplus`; guest mount point: `/mnt/lmdesktopplus`.
- Defaults: 4 vCPUs (cap to `nproc - 1`), 8 GiB RAM, 40 GiB disk, UEFI, NAT, Spice.
- Do not commit secrets; do not force-push; do not amend unless user asks.
- Source of truth for behavior: `docs/superpowers/specs/2026-07-20-lmdesktopplus-vm-lab-design.md`.

---

## File structure

```
scripts/vm/create-mint-guest.sh
scripts/vm/attach-share.sh
scripts/vm/destroy-mint-guest.sh
scripts/vm/common.sh
docs/vm-lab.md
tests/test-vm-scripts.sh
tests/smoke-structure.sh          # extend
README.md                         # short VM lab pointer
```

---

### Task 1: Shared VM helpers + structure test hooks

**Files:**
- Create: `scripts/vm/common.sh`
- Modify: `tests/smoke-structure.sh`
- Create: `tests/test-vm-scripts.sh` (stub assertions for paths)

**Interfaces:**
- Produces: `vm_repo_root`, `vm_require_cmd`, `vm_log_*`, `LAB_PREFIX=lmdesktopplus-`, `assert_lab_name`

- [ ] **Step 1: Extend smoke-structure expectations (will fail until scripts exist)**

Add to `tests/smoke-structure.sh`:

```bash
need "scripts/vm/create-mint-guest.sh"
need "scripts/vm/attach-share.sh"
need "scripts/vm/destroy-mint-guest.sh"
need "scripts/vm/common.sh"
need "docs/vm-lab.md"
```

- [ ] **Step 2: Write `scripts/vm/common.sh`**

```bash
#!/usr/bin/env bash
# Shared helpers for LMDesktopPlus VM lab scripts.
LAB_PREFIX="${LAB_PREFIX:-lmdesktopplus-}"
DEFAULT_NAME="${DEFAULT_NAME:-lmdesktopplus-mint}"
VIRTIOFS_TAG="${VIRTIOFS_TAG:-lmdesktopplus}"
GUEST_MOUNT="${GUEST_MOUNT:-/mnt/lmdesktopplus}"

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
      vm_log_err "missing required command: $c"
      return 1
    }
  done
}

assert_lab_name() {
  local name="$1"
  [[ "$name" == "$LAB_PREFIX"* ]] || {
    vm_log_err "refusing non-lab domain '$name' (must start with $LAB_PREFIX)"
    return 1
  }
}

vm_cap_vcpus() {
  local want="$1" host
  host="$(nproc 2>/dev/null || echo 2)"
  local max=$((host > 1 ? host - 1 : 1))
  if (( want > max )); then echo "$max"; else echo "$want"; fi
}
```

- [ ] **Step 3: Run smoke — expect FAIL on missing scripts/docs**

Run: `bash tests/smoke-structure.sh`  
Expected: `MISSING: scripts/vm/...` and/or `docs/vm-lab.md`

---

### Task 2: `create-mint-guest.sh`

**Files:**
- Create: `scripts/vm/create-mint-guest.sh`

**Interfaces:**
- Consumes: `scripts/vm/common.sh`
- Flags: `--name`, `--iso`, `--ram`, `--vcpus`, `--disk-gb`, `--repo-path`, `--dry-run`, `-h`
- Env: `MINT_ISO`, `DRY_RUN`

- [ ] **Step 1: Implement create script**

Behavior:
1. Resolve repo path (default `vm_repo_root`)
2. Require `--iso` or `MINT_ISO` existing file
3. Cap vCPUs; assert lab name
4. Build `virt-install` argv with: qcow2 disk in default pool or `$HOME/VirtualMachines`, UEFI, NAT, Spice graphics, virtio-gpu video, `--memorybacking source.type=memfd,access.mode=shared`, filesystem virtiofs source=repo target=tag
5. If domain already exists: error unless documenting recreate via destroy first
6. `--dry-run`: print argv and exit 0 without running

- [ ] **Step 2: Dry-run without virt stack**

Run: `MINT_ISO=/tmp/fake.iso` touch fake; `./scripts/vm/create-mint-guest.sh --iso /tmp/fake.iso --dry-run`  
Expected: prints planned `virt-install` line; exit 0 (may warn if virt-install missing only when not dry-run — on dry-run allow missing virt-install)

- [ ] **Step 3: Refuse bad names**

Run: `./scripts/vm/create-mint-guest.sh --name evil --iso /tmp/fake.iso --dry-run`  
Expected: non-zero; error about lab prefix

---

### Task 3: `attach-share.sh` + `destroy-mint-guest.sh`

**Files:**
- Create: `scripts/vm/attach-share.sh`
- Create: `scripts/vm/destroy-mint-guest.sh`

**Interfaces:**
- attach: `--name`, `--repo-path`, `--dry-run`; prints guest mount commands
- destroy: `--name`, `--force`, `--dry-run`; requires `--force`; prefix gate; `virsh destroy`/`undefine --remove-all-storage` or equivalent

- [ ] **Step 1: Implement attach-share**

If domain missing: error. If filesystem already present: log and continue. Else `virsh attach-device` or document XML edit; always print:

```bash
sudo mkdir -p /mnt/lmdesktopplus
sudo mount -t virtiofs lmdesktopplus /mnt/lmdesktopplus
```

and fstab line: `lmdesktopplus /mnt/lmdesktopplus virtiofs defaults 0 0`

- [ ] **Step 2: Implement destroy**

Without `--force`: refuse. With `--force` and lab name: destroy + undefine with storage removal. `--dry-run`: print actions only.

- [ ] **Step 3: Test destroy gates**

```bash
./scripts/vm/destroy-mint-guest.sh --name lmdesktopplus-mint --dry-run   # fail: no --force
./scripts/vm/destroy-mint-guest.sh --name other-vm --force --dry-run     # fail: prefix
./scripts/vm/destroy-mint-guest.sh --name lmdesktopplus-mint --force --dry-run  # ok print
```

---

### Task 4: Docs + README + automated tests

**Files:**
- Create: `docs/vm-lab.md`
- Modify: `README.md` (add “VM lab” section linking docs)
- Create: `tests/test-vm-scripts.sh`
- Modify: `tests/smoke-structure.sh` (already updated in Task 1)

- [ ] **Step 1: Write `docs/vm-lab.md`**

Cover: host packages (`qemu-kvm`, `libvirt-daemon-system`, `virt-manager`, `virtinst`), add user to `libvirt`/`kvm`, download Mint Cinnamon ISO, create guest, Virt-Manager install, mount share, git clone option, `./install.sh`, snapshots (`virsh snapshot-create-as`, revert), destroy/recreate, lab mode philosophy.

- [ ] **Step 2: Write `tests/test-vm-scripts.sh`** exercising dry-run/prefix/`--force` gates without needing libvirt.

- [ ] **Step 3: Run `bash tests/smoke-structure.sh` and `bash tests/test-vm-scripts.sh` — expect PASS**

- [ ] **Step 4: Point README at `docs/vm-lab.md`**

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| create via virt-install | Task 2 |
| attach virtiofs | Task 3 |
| destroy with prefix + force | Task 3 |
| dual sync documented | Task 4 |
| lab mode / snapshots | Task 4 |
| dry-run | Tasks 2–3 |
| smoke tests | Tasks 1, 4 |
