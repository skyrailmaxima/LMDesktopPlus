# Changelog

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
