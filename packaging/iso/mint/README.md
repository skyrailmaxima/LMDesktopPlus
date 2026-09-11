# LMDesktopPlus Mint respin (live-build)

A scripted, reproducible Linux Mint respin that boots into the LMDesktopPlus
vapor//matrix desktop with **all packaged software preinstalled**.

`build-iso.sh` assembles a [live-build](https://manpages.debian.org/live-build)
configuration and (on a proper host) emits `dist/lmdesktopplus-mint-<ver>.iso`.

## What the spin bakes in

- **Full software set** — the `lmdesktopplus-desktop` metapackage plus the
  `lmdesktopplus` control center are bundled as local `.deb`s in
  `config/packages.chroot/`. live-build installs them and resolves their
  dependencies (terminals, launcher, monitors, media, network/bluetooth,
  screenshot/clipboard tools, the optional Hyprland session, the JetBrains Mono
  UI font — the whole set from `packaging/software-manifest.json`) from the
  archive. Preinstall == install one metapackage.
- **Default vapor//matrix look** — `config/includes.chroot/etc/dconf/` seeds
  system dconf defaults: the `vapor-matrix.png` wallpaper (injected into
  `/usr/share/backgrounds/lmdesktopplus/`) and a dark Cinnamon/GNOME theme.
- **Autostart** — the control center's XDG autostart entry is dropped into
  `/etc/xdg/autostart/` so the UI launches at login.
- **Optional Hyprland session** — registered in `/usr/share/wayland-sessions/`;
  the finalize hook rewrites its `Exec`/`TryExec` to the detected binary.
- **Trademark-safe branding** — `/etc/lmdesktopplus/spin-release` records the
  spin identity ("LMDesktopPlus Spin", vapor//matrix) without touching
  `/etc/os-release`, so Mint's update tooling keeps working and no Linux Mint
  trademarks are asserted.

## Layout

```
packaging/iso/mint/
  build-iso.sh                     orchestrator (--check | --dry-run | --build)
  config/                          committed live-build customization
    hooks/normal/50-lmdesktopplus.hook.chroot   finalize (dconf/session/caches)
    includes.chroot/
      etc/dconf/profile/user       dconf: user + system-db:local
      etc/dconf/db/local.d/00-lmdesktopplus-vapor-matrix   wallpaper + dark look
      etc/lmdesktopplus/spin-release   branding marker
```

The `.debs` and branded assets (wallpaper, Hyprland session, autostart entry)
are **not** committed — `build-iso.sh` builds/copies them from their canonical
sources into a staging config under `build/iso/mint/config/` at build time.

## Building

```sh
# Linux cloud agent / CI: build the .debs and assemble + validate the staging
# config. No root, no live-build, no /dev/kvm required.
./packaging/iso/mint/build-iso.sh --check

# Show the exact live-build commands the real build would run.
./packaging/iso/mint/build-iso.sh --dry-run

# Emit the ISO (needs root + the `live-build` package on the builder host):
sudo ./packaging/iso/mint/build-iso.sh --build
# -> dist/lmdesktopplus-mint-<ver>.iso
```

Bootstrap base/mirror are overridable via env (Mint 22.x tracks Ubuntu 24.04):

```sh
LB_DISTRIBUTION=noble \
LB_MIRROR=http://archive.ubuntu.com/ubuntu/ \
LB_ARCHIVE_AREAS="main restricted universe multiverse" \
  sudo ./packaging/iso/mint/build-iso.sh --build
```

## Boot validation

This cloud agent has **no `/dev/kvm`**, so `--build` is gated to a host with
root + live-build, and boot-testing runs on the KVM Mint lab (Track 1) — see
[docs/vm-lab.md](../../../docs/vm-lab.md). CI runs `--check` on every push and
gates the actual ISO build behind a tag/manual trigger on a capable runner.

## Interactive fallback: Cubic

For a one-off respin without live-build, [Cubic](https://github.com/PJ-Singh-001/Cubic)
on a real Linux Mint ISO is the supported interactive path: in the chroot,
`apt install ./lmdesktopplus_<ver>_all.deb ./lmdesktopplus-desktop_<ver>_all.deb`
(from `dist/`), then copy the same `config/includes.chroot/` overlay and run
`dconf update`. The scripted live-build route above is preferred for CI and
reproducibility.
