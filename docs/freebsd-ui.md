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

## Out of scope (Linux rice)

- `./install.sh` Mint Cinnamon/Hyprland theming
- NetworkManager (`nmcli`), apt Suggests vault, Bubblewrap agent isolation
- amdgpu sysfs and most `/sys`/`/proc` adapters

Those paths already return unavailable / command_error when tools are missing.
