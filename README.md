# LMDesktopPlus

LMDesktopPlus is an installable **vapor//matrix machine UI and Linux Mint rice**.
It keeps Cinnamon as the practical daily-driver desktop, can add an optional
Hyprland session, and supplies a local control center for system telemetry,
application launchers, agent workspaces, NetworkManager, media, settings, and
desktop integration.

Version **0.6.7** adds AMD GPU metrics (`rocm-smi` + amdgpu sysfs) alongside
NVIDIA, on top of the 0.6.6 preopt pass. Live matrix wallpaper defaults **on**
(START still explicit).

## Install the machine UI

The Debian package is the cleanest system-wide installation:

```bash
sudo apt install ./lmdesktopplus_0.6.7_all.deb
lmdesktopplus
```

Launch modes:

```bash
lmdesktopplus             # embedded GTK/WebKit window
lmdesktopplus --kiosk     # fullscreen control center
lmdesktopplus --browser   # local browser fallback
```

For a user-local installation from source:

```bash
./scripts/install-ui.sh
~/.local/bin/lmdesktopplus
```

## Install the complete Mint rice

```bash
./install.sh                  # Cinnamon theme + machine UI (primary)
./install.sh --with-hyprland  # distro Hyprland packages only, then link configs
./install.sh --with-hyprland --allow-community-ppa  # opt-in community PPA fallback
./install.sh --no-ui          # rice/configuration only
./install.sh --dry-run        # print the complete plan without changing files
./stow.sh --dry-run           # optional GNU stow frontend (install.sh remains primary)
```

Optional Debian Suggests (Bluetooth, CUPS, swayidle, mpvpaper, …) are mapped in
[`docs/suggests.md`](docs/suggests.md).

On Mint, LightDM often hides Wayland sessions — start Hyprland from a TTY
(`Ctrl+Alt+F3` → `./scripts/start-hyprland-tty.sh`). See
[`docs/install-notes.md`](docs/install-notes.md).

`./switch.sh` installs the full setup with Hyprland and prepares a safe TTY
switch workflow. Cinnamon remains available and is the recommended fallback.

## VM lab (host → Mint guest)

To iterate the rice and machine UI inside a disposable Linux Mint VM
(QEMU/KVM + Virt-Manager, virtiofs share + git):

```bash
# on the host, after installing libvirt/virt-manager (see docs)
./scripts/vm/create-mint-guest.sh --iso /path/to/linuxmint-cinnamon.iso
```

Full host setup, mount instructions, snapshots, and destroy/recreate:
[`docs/vm-lab.md`](docs/vm-lab.md).

## Functional machine UI

The local control center includes:

- Internal lock scene plus an allowlisted system-lock action.
- Live CPU, memory, disk, load, uptime, network, temperature, battery, and
  supported GPU telemetry.
- Rolling system-monitor charts.
- Application launchers for terminal, tmux, editor, browser, Rofi, file
  manager, settings, and monitoring tools.
- Agent registry with dedicated homes, configurable workspaces, executable
  detection, and optional Bubblewrap filesystem/network isolation.
- NetworkManager Wi-Fi scanning, connection, and disconnection.
- MPRIS media status and controls through `playerctl`.
- Persistent appearance, behavior, feature, and agent configuration.
- App vault (`FEATURE_PACKAGES`) with optional confirmed `pkexec` apt installs.
- Generated Hyprland chord overlay editor and agent peer roster CRUD.
- Generated GTK 3, GTK 4, and Hyprland appearance overlays.
- A live Digitalvapor component laboratory for checking new panel features
  before they are wired into production screens.

## Security model

The frontend talks to a Python standard-library HTTP server bound to
`127.0.0.1` on a random port. Each launch receives a random token through a
CSP-compatible metadata field, and every API request must present it.

The backend has no arbitrary shell endpoint. Actions and launch targets are
allowlisted. Wi-Fi passwords are passed directly to NetworkManager and are not
persisted by LMDesktopPlus. Power actions remain disabled until explicitly
enabled in settings.

Bubblewrap is useful process/filesystem isolation for agents, but it is not a
virtual machine and does not protect against kernel compromise.

## Digitalvapor design system

Frontend assets live in:

```text
src/lmdesktopplus/static/digitalvapor.css
src/lmdesktopplus/static/digitalvapor.js
src/lmdesktopplus/static/style.css
src/lmdesktopplus/static/app.js
```

`digitalvapor.css` owns reusable tokens, utilities, components, effects, and
chrome. `style.css` contains LMDesktopPlus-specific layouts and compatibility
rules. `digitalvapor.js` provides dependency-free rain, tabs, dropdowns,
context menus, dialogs, and toasts. `app.js` handles machine state and API
operations.

Embedded webfont payloads are deliberately not redistributed. The UI uses
installed JetBrains Mono, DotGothic16, and Zen Dots families when available,
with standard Linux fallbacks. The full rice installer can install or fetch
those font families separately.

See [`docs/digitalvapor-design-system.md`](docs/digitalvapor-design-system.md)
for component conventions.

## Configuration

Persistent user files:

```text
~/.config/lmdesktopplus/settings.json
~/.config/lmdesktopplus/agents.json
~/.config/lmdesktopplus/hypr-generated.conf
~/.local/share/lmdesktopplus/agents/<name>/
```

Generated appearance overlays:

```text
~/.config/gtk-3.0/lmdesktopplus-generated.css
~/.config/gtk-4.0/lmdesktopplus-generated.css
~/.config/lmdesktopplus/hypr-generated.conf
```

## Cinnamon and Hyprland

| Session | Role | Notes |
|---|---|---|
| Cinnamon | Default Mint desktop | GTK CSS, wallpaper, dark-theme hints, shared terminal/launcher configuration |
| Hyprland | Optional tiling session | Matching Hyprland, Waybar, Rofi, Kitty, wallpaper, and generated appearance overlay |

Hyprland support is fail-soft. If it cannot be installed or detected, the
Cinnamon and machine-UI installation still completes.

## Repository layout

```text
src/lmdesktopplus/            Python backend and static machine UI
packages/shared/              GTK, Kitty, Rofi, tmux, Starship, Bash
packages/cinnamon/            Cinnamon integration notes
packages/hyprland/            Hyprland, Waybar, and session files
palette/                      Canonical vapor-matrix palette
scripts/                      User installer, desktop helpers, and VM lab
scripts/vm/                   QEMU/KVM Mint guest create/attach/destroy
packaging/                    Debian package builder
docs/                         Architecture, design system, install notes
tests/                        Python, shell, frontend, and package checks
assets/wallpapers/            Shared wallpaper source
```

## Build packages

```bash
./packaging/build-deb.sh
python3 -m build --wheel
```

The resulting artifacts are placed under `dist/`.

## Test

```bash
./tests/run-all.sh
```

The suite validates repository structure, shell behavior, Python compilation,
API authorization, static asset delivery, settings, NetworkManager parsing,
JavaScript syntax, installer dry-run behavior, Debian contents, and the absence
of cached bytecode or bundled font files.

## Uninstall

```bash
./uninstall.sh
```

The uninstaller restores known configuration paths from the newest backup when
possible and removes LMDesktopPlus-owned links and launchers. It intentionally
does not remove apt packages, the backup tree, or unrelated user settings.

## License

[MIT](LICENSE) © 2026 skyrailmaxima and LMDesktopPlus contributors
