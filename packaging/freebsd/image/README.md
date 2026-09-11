# LMDesktopPlus FreeBSD install image

A scripted, reproducible FreeBSD install image that boots into the LMDesktopPlus
vapor//matrix control center with **all packaged software preinstalled**.

`build-image.sh` assembles a [`poudriere image`](https://github.com/freebsd/poudriere/wiki/poudriere-image)
overlay + package list and (on a FreeBSD host) emits
`dist/lmdesktopplus-freebsd-<ver>.img`.

## What the image bakes in

- **Full software set** — `packages.list` preinstalls the
  `lmdesktopplus-desktop` metaport, which `RUN_DEPENDS` on the LMDesktopPlus
  control center plus the complete vapor//matrix peer set (from
  `packaging/software-manifest.json`), resolved from the local poudriere pkg
  repo. Plus `xorg` + `xinit` + `dbus` + `feh` (the display stack the UI needs
  but that is not itself a UI dependency).
- **Local pkg repo** — `overlay/usr/local/etc/pkg/repos/lmdp.conf` points pkg at
  `file:///usr/local/lmdp-pkgrepo`, the repo produced by
  `packaging/freebsd/poudriere/build-repo.sh` (Phase 4).
- **UI autostart** — a firstboot rc.d hook (`lmdp_autologin`) wires ttyv0 to an
  autologin getty; root's `.profile` runs `startx` on that console; `.xinitrc`
  paints the branded background and `exec`s the control center. Other ttys (ssh,
  serial) still drop to a shell so the box stays administrable.
- **Default vapor//matrix look** — the `vapor-matrix.png` wallpaper is injected
  into `/usr/local/share/backgrounds/lmdesktopplus/`. The XDG autostart entry is
  also shipped (Exec pointed at `/usr/local/bin/lmdesktopplus`) for when a full
  desktop session is used instead of the kiosk `.xinitrc`.
- **Trademark-safe branding** — `/etc/lmdesktopplus/spin-release` records the
  spin identity without touching `/etc/os-release` or FreeBSD version files.

## Layout

```
packaging/freebsd/image/
  build-image.sh          orchestrator (--check | --dry-run | --build)
  packages.list           packages fed to `poudriere image -f`
  overlay/                committed image overlay (`poudriere image -c`)
    etc/rc.conf.local            additive rc (dbus)
    etc/lmdesktopplus/spin-release   branding marker
    root/.xinitrc, root/.profile     autologin -> startx -> control center
    usr/local/etc/pkg/repos/lmdp.conf   local poudriere repo
    usr/local/etc/rc.d/lmdp_autologin   firstboot: ttyv0 autologin
```

The wallpaper, XDG autostart entry, and the `firstboot` sentinel are injected by
`build-image.sh` into a staging overlay under `build/freebsd-image/` (not
committed).

## Building

```sh
# Any host (incl. this Linux cloud agent): assemble + validate the overlay and
# package list. No FreeBSD, poudriere, or root required.
./packaging/freebsd/image/build-image.sh --check

# Show the exact poudriere image command the real build would run.
./packaging/freebsd/image/build-image.sh --dry-run

# Emit the image (FreeBSD host with poudriere + root + the local repo):
#   1. build the local pkg repo (Phase 4):
sudo ./packaging/freebsd/poudriere/build-repo.sh
#   2. build the image:
sudo ./packaging/freebsd/image/build-image.sh --build
# -> dist/lmdesktopplus-freebsd-<ver>.img
```

Image knobs are overridable via env: `IMG_TYPE` (usb/iso/…), `IMG_SIZE`,
`IMG_HOST`, `JAIL`, `PORTS`.

## Why this cannot build here

This cloud agent is Linux-only, so `--build` is gated to a FreeBSD host and the
image cannot be produced or boot-tested here. `--check`/`--dry-run` validate the
recipe on Linux; CI gates the real build behind a tag/manual trigger on a
FreeBSD runner (Phase 7).

## Alternatives to poudriere image

`release(7)` (`cd /usr/src/release && make release` with a custom pkg list and
overlay) or `mkimg` (assemble a UFS/ZFS rootfs, then wrap it into a bootable
memstick) produce equivalent artifacts. `poudriere image` is preferred here
because it reuses the Phase 4 poudriere jail/repo directly and is fully
scripted.
