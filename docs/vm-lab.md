# LMDesktopPlus VM lab

Reproducible **QEMU/KVM + Virt-Manager** lab for iterating LMDesktopPlus on a
real Linux Mint Cinnamon desktop. Guests named `lmdesktopplus-*` are
disposable (lab mode): hotswap configs via virtiofs, snapshot when useful,
destroy/recreate when you want a clean slate.

Design: [`docs/superpowers/specs/2026-07-20-lmdesktopplus-vm-lab-design.md`](superpowers/specs/2026-07-20-lmdesktopplus-vm-lab-design.md)

## Cloud / no-KVM smoke guest

Cursor Cloud agents (and other nested virt hosts) often lack `/dev/kvm`, so the
Mint Virt-Manager lab cannot run there. Use the headless Ubuntu cloud smoke
guest instead — it boots under QEMU TCG, shares the repo via 9p, runs
`./tests/run-all.sh`, then applies the UI build (`install-ui.sh` + local `.deb`):

```bash
./scripts/vm/smoke-cloud-guest.sh
# optional: --keep  (leave QEMU up; ssh -p 2222 ubuntu@127.0.0.1  password: ubuntu)
# optional: --skip-apply  (tests only)
```

This validates packaging + unit tests + installable UI entrypoints in a clean
guest. It is **not** a substitute for the Mint Cinnamon rice lab below.

## Host prerequisites

On the developer machine (Pop!_OS / Ubuntu / similar):

```bash
sudo apt update
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients \
  bridge-utils virt-manager virtinst
sudo usermod -aG libvirt,kvm "$USER"
```

Log out and back in (or reboot) so group membership applies. Check:

```bash
virsh list --all
# should not require sudo once groups are active
```

Download a **Linux Mint Cinnamon** ISO from the [official downloads](https://linuxmint.com/download.php) and note the path (e.g. `~/Downloads/linuxmint-22.1-cinnamon-64bit.iso`).

## Create the guest

From the repo root on the host:

```bash
./scripts/vm/create-mint-guest.sh \
  --iso ~/Downloads/linuxmint-*.iso \
  --dry-run          # optional: print virt-install plan

./scripts/vm/create-mint-guest.sh --iso /path/to/linuxmint.iso
```

Defaults: domain `lmdesktopplus-mint`, 8 GiB RAM, 4 vCPUs (capped to
`nproc - 1`), 40 GiB qcow2 under `~/VirtualMachines/`, UEFI, NAT, Spice,
virtiofs share of the repo (tag `lmdesktopplus`).

Open **Virt-Manager**, open the guest console, and finish the Mint installer.
After first boot of the installed system, mount the share (below).

### If virt-install complains about os-variant

List variants with `osinfo-query os | grep -i mint` and re-run with a matching
name, or ignore detection — the create script uses `detect=on,name=linuxmint22`
as a best-effort hint.

## Mount the host repo (virtiofs)

Inside the guest:

```bash
sudo mkdir -p /mnt/lmdesktopplus
sudo mount -t virtiofs lmdesktopplus /mnt/lmdesktopplus
cd /mnt/lmdesktopplus
./install.sh
```

Persistent mount — add to `/etc/fstab`:

```
lmdesktopplus /mnt/lmdesktopplus virtiofs defaults 0 0
```

If the share is missing on an older guest, from the host:

```bash
./scripts/vm/attach-share.sh --name lmdesktopplus-mint
```

## Dual sync (git)

Virtiofs is for fast host→guest iteration. For clean-install tests without the
share (or to push from the guest):

```bash
mkdir -p ~/src
git clone https://github.com/skyrailmaxima/LMDesktopPlus.git ~/src/LMDesktopPlus
cd ~/src/LMDesktopPlus
./install.sh
```

Host Cursor edits land on the share path; commit/push from the host clone
(recommended) so GitHub stays the source of truth.

## Lab mode: snapshots, hotswap, destroy

**Hotswap:** edit on the host → files appear under `/mnt/lmdesktopplus` →
re-run `./install.sh` or reload apps (kitty, etc.). Most theme changes do not
need a guest reboot.

**Snapshot** (after a good Mint + install baseline):

```bash
virsh snapshot-create-as lmdesktopplus-mint clean-rice \
  "Mint + LMDesktopPlus install baseline"
# later:
virsh snapshot-revert lmdesktopplus-mint clean-rice
```

**Full rebuild:**

```bash
./scripts/vm/destroy-mint-guest.sh --name lmdesktopplus-mint --force
./scripts/vm/create-mint-guest.sh --iso /path/to/linuxmint.iso
```

Destroy refuses names outside `lmdesktopplus-*` and requires `--force`.

## Flags cheat sheet

| Script | Useful flags |
|--------|----------------|
| `create-mint-guest.sh` | `--iso`, `--name`, `--ram`, `--vcpus`, `--disk-gb`, `--repo-path`, `--dry-run` |
| `attach-share.sh` | `--name`, `--repo-path`, `--dry-run` |
| `destroy-mint-guest.sh` | `--name`, `--force`, `--dry-run` |

Env: `MINT_ISO`, `DRY_RUN=1`, `LMDESKTOPPLUS_VM_DISK_DIR`.

## Next: UI iteration

With Cinnamon themed via `./install.sh`, compare against
`assets/preview/NeonRice-Vaporwave-Matrix-Rice.html` and iterate packages under
`packages/shared/`, `packages/cinnamon/`, and optionally `packages/hyprland/`.
See [`docs/install-notes.md`](install-notes.md) for Hyprland on Mint.
