# FreeBSD UI package

LMDesktopPlus can ship the **vapor//matrix machine UI** on FreeBSD. The Mint
rice (`install.sh`, Cinnamon/Hyprland overlays, apt vault) remains Linux-only;
adapters that need Linux tools fail soft.

## What works on FreeBSD

| Area | Backend |
|---|---|
| Metrics (CPU, RAM, net, temp, battery, uptime) | `sysctl` / `netstat` via `platform_freebsd` |
| Disk / load | `os.statvfs` / `os.getloadavg` |
| GPU | `nvidia-smi` / `rocm-smi` when present; amdgpu sysfs is Linux-only |
| Lock | `loginctl`, xscreensaver, xlock, swaylock, i3lock (first success) |
| Power | `zzz` / `acpiconf -s 3`, `shutdown -r/-p now` (when enabled in settings) |
| Launchers | kitty, alacritty, xterm, firefox, tmux, btop/htop/top, … |
| Embedded UI | GTK3 + WebKit2 via PyGObject when ports are installed |
| Fallback | `lmdesktopplus --browser` on loopback |

## Dependencies (ports)

```text
python3 >= 3.10
devel/py-gobject3
www/webkit2-gtk (optional for embedded window)
```

Useful peers: `x11/kitty` or `x11/alacritty` or `x11/xterm`, `sysutils/tmux`,
`sysutils/btop`, `www/firefox`.

## Build the UI package (any host)

Stages `/usr/local` layout and writes an xz tarball (for FreeBSD install or CI):

```bash
./packaging/build-freebsd-ui.sh
# -> dist/lmdesktopplus-<version>-freebsd.txz
sudo tar -xJf dist/lmdesktopplus-*-freebsd.txz -C /
```

On FreeBSD with a ports tree checkout of this skeleton:

```bash
cd packaging/freebsd
make WRKSRC=/path/to/LMDesktopPlus stage
```

## User-local install

Same as Linux:

```bash
./scripts/install-ui.sh
~/.local/bin/lmdesktopplus --browser
```

## Full desktop metaport + local pkg repo

For a full FreeBSD spin (Phase 4/6) the whole peer set is expressed as a
generated metaport driven by [`packaging/software-manifest.json`](software-manifest.md):

```bash
# Generate x11-wm/lmdesktopplus-desktop (RUN_DEPENDS = UI port + peers)
./packaging/build-freebsd-metaport.sh /path/to/overlay/x11-wm/lmdesktopplus-desktop

# Build a local poudriere pkg repo (FreeBSD host only; prints a plan elsewhere)
./packaging/freebsd/poudriere/build-repo.sh
# then: pkg install lmdesktopplus-desktop
```

`pkg-origins.json` maps each manifest FreeBSD package to its ports origin;
Linux-only peers (NetworkManager, bubblewrap, BlueZ, Mint Update) are omitted.

## Full install image (Phase 6)

A bootable FreeBSD image that comes up into the control center is scripted under
[`packaging/freebsd/image/`](../packaging/freebsd/image/README.md) via
`poudriere image` (preinstalls `lmdesktopplus-desktop` + the Xorg/GTK/WebKit
stack from the local repo, autostarts the UI on ttyv0, applies the vapor//matrix
look + trademark-safe branding):

```bash
# Any host: assemble + validate the image overlay/package list.
./packaging/freebsd/image/build-image.sh --check
# FreeBSD host: build the local repo, then the image.
sudo ./packaging/freebsd/poudriere/build-repo.sh
sudo ./packaging/freebsd/image/build-image.sh --build
# -> dist/lmdesktopplus-freebsd-<ver>.img
```

## Out of scope (Linux rice)

- `./install.sh` Mint Cinnamon/Hyprland theming
- NetworkManager (`nmcli`), apt Suggests vault, Bubblewrap agent isolation
- amdgpu sysfs and most `/sys`/`/proc` adapters

Those paths already return unavailable / command_error when tools are missing.
