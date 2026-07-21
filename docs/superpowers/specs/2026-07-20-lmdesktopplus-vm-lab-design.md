# LMDesktopPlus VM Lab Design Spec

**Date:** 2026-07-20  
**Repo:** `skyrailmaxima/LMDesktopPlus`  
**Status:** Approved (Approach 2 + lab mode)  
**Depends on:** `docs/superpowers/specs/2026-07-20-lmdesktopplus-design.md` (rice installer)

## 1. Problem

UI/UX iteration for LMDesktopPlus needs a real Linux Mint Cinnamon desktop (login greeter, sessions, GTK/Cinnamon, optional Hyprland). Host development (Cursor) should stay on the developer machine while the guest remains a disposable lab for install/preview cycles. Rebuilding guests must be cheap so the long-term integrated UI can move fast and break things safely.

## 2. Goals

- Greenfield **QEMU/KVM + Virt-Manager** lab on the host
- **Scripted guest creation** via `virt-install` (`scripts/vm/create-mint-guest.sh`)
- **Virtiofs share** of the host repo clone + **git remotes** inside the guest (dual sync)
- **Lab mode:** hotswap configs, snapshot revert, destroy/recreate for domains named `lmdesktopplus-*`
- Document host prerequisites and guest post-install checklist in `docs/vm-lab.md`
- Enable later UI fidelity work against NeonRice without blocking on Packer/containers

## 3. Non-goals (this phase)

- Fully unattended Mint install (no Packer/Vagrant yet)
- Docker/Podman desktop containers
- Building the full integrated UI product beyond the existing rice + lab tooling
- Auto-installing Hyprland inside the guest
- Touching unrelated libvirt domains

## 4. Architecture

### 4.1 Host ↔ guest workflow

| Layer | Role |
|-------|------|
| Host | Clone repo; edit in Cursor; run `scripts/vm/*.sh`; Virt-Manager for console/install |
| Guest | Mint Cinnamon; mount virtiofs at `/mnt/lmdesktopplus`; optional `~/src/LMDesktopPlus` git clone; run `./install.sh` |

### 4.2 Dual sync

- **Virtiofs** tag `lmdesktopplus` → guest `/mnt/lmdesktopplus` for live iteration
- **Git** clone of `https://github.com/skyrailmaxima/LMDesktopPlus` for clean-install tests and push/pull without the share

### 4.3 Scripts (`scripts/vm/`)

| Script | Role |
|--------|------|
| `create-mint-guest.sh` | Create qcow2 + domain via `virt-install` (UEFI, NAT, Spice, virtiofs, ISO) |
| `attach-share.sh` | Idempotent virtiofs attach + print guest mount/fstab notes |
| `destroy-mint-guest.sh` | Destroy domain + disk for `lmdesktopplus-*` only (`--force` required) |
| (optional helper text) | Snapshot guidance in `docs/vm-lab.md` (`virsh snapshot-create-as` / revert) |

### 4.4 Guest defaults

| Setting | Default |
|---------|---------|
| Name | `lmdesktopplus-mint` |
| vCPUs | 4 (capped to host cores − 1 when smaller) |
| RAM | 8 GiB |
| Disk | 40 GiB qcow2, virtio |
| Firmware | UEFI |
| Display | Spice + virtio-gpu (QXL fallback documented) |
| Network | default libvirt NAT |
| Share | virtiofs `source.dir` = repo root, `target` tag `lmdesktopplus` |

Flags: `--name`, `--iso` / `MINT_ISO`, `--ram`, `--vcpus`, `--disk-gb`, `--repo-path`, `--dry-run`, `--force` (destroy/recreate only).

### 4.5 Lab mode (break / recover)

- Hotswap: host edit → share → re-run `./install.sh` in guest
- Snapshots after first good install (`clean-rice`); revert instead of full reinstall when possible
- Destroy/recreate allowed for `lmdesktopplus-*` with explicit `--force`
- Guest `~/.lmdesktopplus-backup/` remains for mid-session config undo
- Host home outside the share and non-lab domains stay protected

## 5. Success criteria

1. On a host with KVM/libvirt installed, `./scripts/vm/create-mint-guest.sh --iso /path/to/mint.iso` creates a bootable domain (or `--dry-run` prints the exact plan)
2. After Mint install in Virt-Manager, virtiofs mounts at `/mnt/lmdesktopplus` and `./install.sh` runs from the share
3. `./scripts/vm/destroy-mint-guest.sh --name lmdesktopplus-mint --force` removes that lab guest; refuses other names
4. `docs/vm-lab.md` is enough to go greenfield → themed Cinnamon without tribal knowledge
5. Smoke/structure tests cover new script/doc paths

## 6. Risks

| Risk | Mitigation |
|------|------------|
| virtiofs needs shared memory backing | Set memoryBacking shared in create script; document if attach fails |
| User not in `libvirt`/`kvm` groups | Document logout/relogin after group add |
| ISO path missing | Require `--iso` or `MINT_ISO`; fail with clear message |
| Accidental destroy of non-lab VM | Name prefix gate + `--force` |

## 7. Approval

- Approach 2 (scripted `virt-install` + Virt-Manager): approved
- Dual sync (virtiofs + git): approved
- Lab mode (hotswap / snapshot / destroy): approved
- Section 1–2 + lab addendum: approved 2026-07-20
- Build authorization: user “lets build it” 2026-07-20
