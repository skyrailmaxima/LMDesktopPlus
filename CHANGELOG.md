# Changelog

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
