# Changelog

## 0.6.7 — AMD GPU metrics + cloud smoke guest

- GPU sampling priority: `nvidia-smi` → `rocm-smi` CSV → `amdgpu` sysfs
  (`gpu_busy_percent`, VRAM, hwmon temp, product name).
- Shared snapshot shape for AMD and NVIDIA: percent, VRAM used/total MiB,
  temperature °C, source tag (`rocm-smi` / `amdgpu-sysfs`).
- Monitor scene shows a VRAM row when memory fields are present.
- Added `scripts/vm/smoke-cloud-guest.sh` for headless Ubuntu cloud tests when
  `/dev/kvm` is unavailable; `stow.sh` tolerates missing `HOME`.

- GPU sampling priority: `nvidia-smi` → `rocm-smi` CSV → `amdgpu` sysfs
  (`gpu_busy_percent`, VRAM, hwmon temp, product name).
- Shared snapshot shape for AMD and NVIDIA: percent, VRAM used/total MiB,
  temperature °C, source tag (`rocm-smi` / `amdgpu-sysfs`).
- Monitor scene shows a VRAM row when memory fields are present.

## 0.6.6 — Preopt keybinds / actions / agents + poll hosts + file I/O

- Poll hosts outside the adapter fence now use `try_run`: `network.current`,
  `media.status`/`control`, and `system_info` nvidia-smi (`_nvidia_gpu`).
- Command hosts: `keybinds._pulse_hyprland`, `actions.lock` (`first_ok_scan`),
  `theme` hyprctl reload, and `actions.open_path` mkdir are exception-free.
- File I/O: `preopt.try_mkdir` / `try_atomic_write` / `try_atomic_write_json`;
  chord synth, idle/live wallpaper etch, and agents roster save fail soft to
  `command_error` / structured errors.
- Density: shared `wrap_in_terminal(..., directory=)` for agent spawn; keybinds
  `dispatch_allowed`; bwrap `append_existing_binds` (one loop per bind set).

## 0.6.5 — Preopt remaining Stage B–D adapters

- Moved updates, printers, logs, idle, vault, session, and live_wallpaper onto
  `try_run` / `parse_int` / `clamp_int` and ternary fail-soft snapshots so poll
  ticks no longer catch `TimeoutExpired` / `RuntimeError` from host probes.
- Apt upgradable probe treats exit codes `{0, 100}` as success without raising.
- Session lifecycle chip uses an ordered gate table; live wallpaper intensity /
  pid checks use parse helpers. True file I/O (`mkdir`/`touch`/`chmod`) stays
  local `OSError` → `command_error`.

## 0.6.4 — Branchless preoptimized hot paths

- Added `preopt` outcomes (`Outcome`, `RunOutcome`, `try_run`, `first_ok_scan`,
  `parse_int`/`parse_float`/`clamp_int`) so hot adapter paths avoid raising into
  the poll tick.
- Refactored audio, display, processes, vpn, storage, clipboard, capture,
  bluetooth, notifications, wallpaper, and `adapters.envelope` toward ternary
  control flow, preoptimized argv/status tables, and at most one loop per
  subfunction (priority-measured helpers).
- Adapter unit tests mock `lmdesktopplus.preopt.run_capture`.

## 0.6.3 — Comment + unpack pass (dispatch / @use parity)

- Converted remaining if-chain adapters (`audio`, `display`, `wallpaper`,
  `notifications`, `updates`, `session`) to `dispatch_command` hash maps.
- Unpacked dense probe/apply paths (audio backends, brightness probes,
  wallpaper apply steps, capture argv etchers, process sampling, clipboard
  peek/copy maps, peer retune patch map).
- Added `@use` / `register_fn` annotations across Stage A–C adapters, agents
  roster helpers, `adapters.envelope`, and hot JS chrome (`queueAudioVolume`,
  patch bindings, `warmUiFnCache` entries).
- Behavior preserved; fail-soft shapes now prefer `command_error` where
  adapters previously returned bare `{ok:false,error}`.

## 0.6.2 — Stage D Task 23 + live wallpaper default on

- `features.live_wallpaper` default **on** (START from Appearance remains
  explicit; stop still clears the flag).
- Added `docs/suggests.md` mapping Debian Suggests → adapters / vault.
- Added optional `./stow.sh` GNU stow frontend (`--materialize-only` for CI);
  `./install.sh` remains the primary installer.
- Digitalvapor kit Stage C/D stories for idle, printers, logs, live wallpaper,
  vault, chords, peers, and vpn/storage/process chrome.
- Stage D Tasks 19–23 complete.

## 0.6.1 — Live matrix wallpaper (Stage D Task 22)

- Added feature-flagged `LiveWallpaperAdapter` (`features.live_wallpaper`,
  default **off** in 0.6.1; flipped default **on** in 0.6.2): HTML/WebKit
  `DV.rain` window via `--live-wallpaper`, with optional `mpvpaper` when
  `live-matrix.mp4` is present.
- Owned `hypr-live-wallpaper.conf` window rules + launcher script; source line
  appended only into LMDesktopPlus-owned `hyprland.conf`.
- Settings → Appearance live wallpaper panel; Apps vault catalog entry.

## 0.6.0 — Stage D polish (idle, printers, logs)

- Added `IdleAdapter`: owned `swayidle-generated.sh` + `idle-generated.conf`,
  Display timers for lock/sleep, best-effort Cinnamon gsettings idle-delay.
- Added `PrintersAdapter`: read-only `lpstat` status + open printer settings UI.
- Added `LogsAdapter`: capped `journalctl --user` panel on Monitor (HTML-escaped).
- Stage D plan: `docs/superpowers/plans/2026-07-24-stage-d-polish.md`.

## 0.5.0 — Stage C power user complete

- Added `VaultAdapter` with `FEATURE_PACKAGES` hashmap driving the Apps vault;
  install via explicit confirm + `pkexec apt-get install` (never silent root).
- Unified Apps cards with vault detect/installable/apt fields; Debian Suggests
  list optional host tools the vault can request.
- Added `fncache` memory hashmap (`FUNCTION_CACHE` / `LMDPFnCache`) with
  **high use / medium use / low use** function annotations for O(1) UI→operation
  resolve on hot paths (`dispatch_command`, bindings, adapterCommand).
- Stage C complete: VPN, storage, processes, keybind chords, agent peer CRUD,
  and app-vault installs.

## 0.4.6 — Agent peer CRUD (vapor roster)

- Added `POST /api/v1/agents` with ops `create|update|delete` (vapor aliases
  `forge|retune|melt`) for allowlisted peer definitions in `agents.json`.
- Settings → Agents forge form and per-peer retune/melt controls; spawn stays on
  `/api/v1/agents/launch`.
- Command argv tuner rejects shells, paths, and metacharacters; Bubblewrap etch
  rules unchanged.
- Began de-complication renaming + full-line commenting on the peer roster and
  shared `dispatch_command` helper.

## 0.4.5 — Vapor//matrix Hyprland chord editor

- Added `ChordAdapter` (`keybinds`) with synthwave typology commands
  (`scan` / `tune` / `melt` / `synth`) writing only the owned overlay
  `~/.config/lmdesktopplus/hypr-binds.conf` plus vapor overrides in
  `keybinds.json`.
- Settings → Keybinds edits neon combos through Digitalvapor UI rails;
  packaged `hyprland.conf` sources the chord overlay; `install.sh` seeds
  matrix defaults for TTY sessions.
- Best-effort `hyprctl reload` pulse after synth when Hyprland is active.

## 0.4.4 — Stage C adapters (VPN, storage, processes)

- Added VpnAdapter (`nmcli`) for VPN/WireGuard profile list, connect, and
  disconnect without storing credentials.
- Added RemovableStorageAdapter (`lsblk` + `udisksctl`) with device-path
  allowlisting for mount/unmount of removable volumes.
- Added ProcessAdapter (`/proc`) top-N process list and UID-scoped SIGTERM with
  a confirmation dialog in Monitor.
- Documented the Stage C adapter matrix; agent CRUD, keybind editor, and app
  vault installs remain planned for 0.5.0.

## 0.4.3 — Adapter contract hardening

- Normalized adapter snapshots into a typed envelope (`id`, `status`,
  `capabilities`, `state`, `updated_at`, `error`) while keeping flat fields for
  one release of UI compatibility.
- Split `/api/v1/state` into domain endpoints (`core`, `metrics`, `adapters`,
  `network`, `media`, `assets`) with the aggregate path retained for compat.
- Added per-key cache locks, exact Origin/Host checks (reject foreign localhost
  ports and `Origin: null`), and stable `error_code` mapping for adapter
  command failures.
- Clarified session lifecycle (`not_installed` / `ready` / `armed` / `active`)
  with `arm_once` + `disarm` (`arm_hyprland` remains an alias).
- Documented the review branch stack in `docs/branching.md`.

## 0.4.2 — Stage B control center

- Added BluetoothAdapter (`bluetoothctl`) with power, timed scan, connect, and
  disconnect controls in Settings → Network.
- Added NotificationsAdapter with `notify-send` test notifications, local
  do-not-disturb, and best-effort Cinnamon `gsettings` DND sync.
- Added UpdatesAdapter with a 10-minute cached `apt list --upgradable` count,
  Mint Update launcher, and topbar badge.
- Added ClipboardAdapter with Wayland (`wl-clipboard`) / X11 (`xclip`) routing,
  truncated peek, copy/clear, and an in-memory history ring.
- Added CaptureAdapter with `grim`/`slurp` or `gnome-screenshot`, saving only
  under `~/Pictures/lmdesktopplus/`.
- Documented the Stage B adapter matrix and optional Suggests binaries.

## 0.4.0 — Stage A machine controls

- Added an adapter registry and cached host adapters for PipeWire/PulseAudio
  volume and mute, display brightness, session handoff, and wallpaper apply.
- Added authenticated machine-control routes with validated, allowlisted
  commands and fail-soft capability snapshots.
- Added volume, mute, brightness, Hyprland one-shot arming, and wallpaper picker
  controls to the machine UI.
- Added hash-mapped icons and wallpaper assets with lazy thumbnail loading.
- Added `LiveStore` state diffs and a `DiffRenderer` so Desktop and Monitor
  patch live metrics, charts, and adapter fields without rebuilding the scene.
- Documented the adapter contract and optional host-binary matrix.

## 0.3.0 — Digitalvapor design system

- Promoted the expanded Digitalvapor styleguide into maintained, dependency-free
  `digitalvapor.css` and `digitalvapor.js` frontend layers.
- Added semantic tokens, spacing, effects, panels, cards, buttons, tags, fields,
  toggles, choices, segmented controls, sliders, tabs, progress, dropdowns,
  context menus, dialogs, toasts, window chrome, side navigation, and dock
  components.
- Refactored the machine UI to consume shared tokens and component classes across
  dashboards, agents, monitor, media, applications, settings, and navigation.
- Replaced browser-native Wi-Fi password prompts and power confirmations with
  themed modal workflows.
- Expanded the UI Kit into a live component and interaction laboratory.
- Moved the launch token from inline JavaScript to CSP-compatible document
  metadata and retained a restrictive `script-src 'self'` policy.
- Added delegated, safe-text toast, dropdown, tabs, modal, and context-menu
  interactions for dynamically rendered scenes.
- Added reduced-motion behavior and documented the panel implementation contract.
- Excluded embedded font binaries and bundled prototype font payloads from
  distributable source and package artifacts.

## 0.2.0 — Functional machine UI

- Converted the bundled NeonRice design prototype into a maintainable local
  GTK/WebKit control center with a browser fallback.
- Added live CPU, memory, disk, network, GPU, battery, temperature, uptime, and
  host/session reporting from `/proc`, sysfs, and available vendor utilities.
- Added allowlisted launch actions for terminal, tmux, editor, browser, Rofi,
  file manager, system settings, and system monitor.
- Added persistent appearance, behavior, feature, and agent configuration with
  generated GTK 3/4 and Hyprland overlays.
- Added a scoped agent registry with separate homes, configurable workspaces,
  executable detection, and optional Bubblewrap isolation/network separation.
- Added NetworkManager Wi-Fi scan/connect/disconnect and MPRIS media controls.
- Added loopback-only authenticated API service with no arbitrary shell route.
- Added user-local installation, Mint application menu integration, Debian
  package construction, Python wheel metadata, uninstall handling, and tests.
- Preserved the existing Cinnamon-first rice and optional Hyprland workflow.
