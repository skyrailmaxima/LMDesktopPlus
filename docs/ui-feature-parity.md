# UI feature-parity audit

Status: **research / backlog** (no runtime code). This audit compares the
LMDesktopPlus control center against the interaction features users expect from
modern desktop control panels, settings apps, and dashboard tools, then lists a
prioritized backlog to reach parity. It is the reference the "editable, tileable
UI" work (and later UX phases) draws from; **editability is backlog item #1**.

## Method

- Current state is drawn from the shipped frontend
  ([src/lmdesktopplus/static/](../src/lmdesktopplus/static/)) and the ~18
  fail-soft adapters ([src/lmdesktopplus/adapters/](../src/lmdesktopplus/adapters/)).
- "Modern UI" reference points surveyed for expected features: GNOME Settings
  + GNOME Shell, macOS System Settings, Windows 11 Settings, KDE Plasma System
  Settings, and self-hosted dashboards (Grafana, Homarr, Heimdall) for the
  tile/widget dimension.
- Each capability is rated: **Have** (shipped), **Partial** (exists but limited),
  or **Gap** (absent).

## 1. What LMDesktopPlus has today

Grounded in the current build:

- **Scenes**: 11 hardcoded workspaces (desktop, agents, tmux, editor, browser,
  rofi, dotfiles, monitor, apps, settings, ui kit) defined in the `scenes` array
  in [app.js](../src/lmdesktopplus/static/app.js).
- **Live telemetry**: CPU / memory / GPU / network / disk / thermals / power /
  uptime with rolling client-side charts on the Monitor scene.
- **System control adapters**: audio, display brightness, session handoff,
  notifications + DND, clipboard, capture, storage, processes, logs, printers,
  updates, VPN, bluetooth, network (Wi-Fi scan/connect), idle.
- **Appearance**: accent swatches, font, opacity, blur, matrix-rain intensity,
  scanlines, window mode, gaps/rounded/shadows; wallpaper picker + live matrix
  wallpaper; appearance changes bridge to host GTK/Hyprland via generated CSS.
- **Reduced-motion** honored; per-panel empty/error states; basic responsive
  layout; nav a11y (aria-label/aria-current) on dock + workspace strip.
- **Differentiators**: agent registry with per-agent homes + optional Bubblewrap
  isolation, the App Vault (allowlisted `pkexec apt` installs), and a UI Kit
  storybook scene.
- **Security contract**: loopback-only, per-launch `X-LMDP-Token`, strict
  Origin/Host/Sec-Fetch-Site checks; no arbitrary shell endpoint.
- **Persistence**: validated global prefs in `settings.json`; last scene + window
  geometry in `ui-state.json`.

## 2. Gap analysis vs modern UIs

### Layout & personalization
| Capability | Status | Notes |
|---|---|---|
| Customizable dashboard tiles (reorder/hide/resize) | Gap | Panels are hardcoded per `render*()`; no tile registry or per-scene layout store. **(Addressed by this work: reorder/hide + view modes.)** |
| Alternate data visualizations per widget (number / chart / gauge) | Gap | Each panel renders one fixed representation. **(Addressed by this work.)** |
| User-editable text / labels (custom greeting, titles) | Gap | "VAPOR//MATRIX" and scene titles are literals. **(Addressed by this work.)** |
| Theme presets / saved appearance profiles | Gap | Only live accent + sliders; no named presets or export/import. |
| Free-form drag/resize dashboard | Gap | Explicitly out of scope for the first editability slice; candidate follow-up. |
| Per-scene / per-widget settings | Gap | Settings are global only. |

### Findability & navigation
| Capability | Status | Notes |
|---|---|---|
| Global search / command palette | Gap | No way to jump to a setting/action by typing. High value. |
| Settings search | Gap | Settings tabs must be browsed manually. |
| Keyboard shortcut cheatsheet / discoverability | Partial | Digit hotkeys switch scenes; no in-UI shortcut reference. |
| Full keyboard operability of all controls | Partial | Nav is labeled; some custom controls need focus/keyboard audit. |
| Breadcrumbs / deep-linking to a setting | Gap | Scene is restored, but not sub-tab or a specific control. |

### Feedback & help
| Capability | Status | Notes |
|---|---|---|
| Toasts / transient feedback | Have | `toast()` / Digitalvapor toast. |
| Tooltips / inline help on controls | Gap | Controls rely on labels only. |
| Onboarding / first-run tour | Gap | No guided intro for a fresh spin. |
| Undo / redo for changes | Gap | Setting changes apply immediately with no undo. |
| Confirmation for destructive actions | Partial | Some (power) gated; not uniform. |
| Notification center / history | Partial | DND exists; no persistent notification log surface. |

### Accessibility & internationalization
| Capability | Status | Notes |
|---|---|---|
| Reduced motion | Have | Matrix rain + CSS animations gated. |
| Nav landmarks / aria on chrome | Partial | Dock + workspace labeled; broader ARIA/roles audit pending. |
| High-contrast / light theme | Gap | Vapor//matrix dark only. |
| Screen-reader pass (live regions scoped) | Partial | Over-broad live region already removed; needs a dedicated SR pass. |
| Font scaling / density options | Gap | Font family selectable; no size/density control. |
| Localization / i18n framework | Gap | English + decorative JP glyphs only; no translation layer. |

### Data & state
| Capability | Status | Notes |
|---|---|---|
| Live polling of system state | Have | Poll + `DiffRenderer` incremental updates. |
| Client-side history/charts | Partial | Ring buffer in memory; not persisted or configurable window. |
| Export / import of config | Gap | `settings.json` is hand-editable but no in-UI export/import. |
| Per-widget refresh interval | Gap | Single global `poll_interval_ms`. |

## 3. Prioritized backlog

Ordered by value-to-effort; the first item is the current work.

1. **Editability: tiles + view modes + editable text** (in progress). Tile
   framework, per-tile number/chart/gauge switching, reorder/hide persisted per
   scene, rotating greeting + editable scene titles.
2. **Command palette / global search** - fuzzy jump to any scene, setting, or
   allowlisted action; also a natural home for keyboard discoverability.
3. **Settings search + deep-linking** - filter controls by keyword; restore
   sub-tab and scroll-to-control.
4. **Theme presets + export/import** - named appearance profiles (incl. a
   high-contrast/light option) and config export/import built on `settings.json`.
5. **Tooltips + first-run onboarding** - inline help on controls and a short
   guided tour for fresh spins.
6. **Accessibility pass** - full keyboard operability, ARIA roles, screen-reader
   review, font-size/density.
7. **Notification center** - persistent, filterable notification/event history.
8. **Free-form dashboard (drag/resize, add/remove tiles)** - the heavier
   dashboard evolution once the tile framework is in place.
9. **Per-widget refresh + persisted history windows.**
10. **Localization/i18n framework.**

## 4. Non-goals / guardrails

- Preserve the loopback + per-launch-token + Origin/Host security contract for
  any new endpoint or capability.
- Keep the frontend framework-free (no SPA framework / heavy drag libs) so it
  stays auditable and testable under the Xvfb smoke harness.
- Defaults must stay inert: new personalization features ship off/neutral so an
  untouched install renders exactly as today.
