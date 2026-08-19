# Interface design review — refresh + what to leverage from the GUI builds

Status: **discussion / proposal** (no runtime code added by this doc). This is a
fresh look at the LMDesktopPlus interface on `feature/lmdesktopplus`, a survey of
what the more advanced "GUI builds" on sibling branches already ship, and a
prioritized shortlist of theme elements and features worth pulling into the
project.

## 1. Where the interface stands today (`feature/lmdesktopplus`)

This branch is the **minimal Bash rice**: it themes Cinnamon (and optionally
Hyprland) by symlinking terminal/app configs, materializing a wallpaper, and
applying `gsettings`. The "interface" is therefore the *themed desktop itself*,
defined by:

- `palette/vapor-matrix.theme` — the canonical vapor//matrix palette (source of truth).
- `assets/preview/NeonRice-Vaporwave-Matrix-Rice.html` — a self-contained mockup of the intended look.
- `packages/shared/*` — kitty, rofi, tmux, starship, GTK 3/4 CSS that hard-code matching hex values.

There is **no first-party GUI application** here yet — no control panel, no
launcher surface, no settings UI. Appearance is static and edited by hand in the
config files.

## 2. The "other GUI builds" (sibling branches / `origin/main`)

Several branches build a full **machine UI / control center** on top of the same
rice. `origin/main` is the furthest along (**v0.6.9**) and was run and toured
live during this review (see screenshots/video in the PR). It is a local
**Python standard-library HTTP server** (`src/lmdesktopplus/`) rendering a
framework-free web frontend, launched as an embedded GTK/WebKit window, kiosk,
or browser fallback:

```bash
PYTHONPATH=src python3 -m lmdesktopplus --browser   # no third-party deps
```

Branch progression (all diffed against `feature/lmdesktopplus`):

| Branch | Theme |
|---|---|
| `feature-adapter-contract` / `feature-control-center-core` | Core server + adapter contract + first scenes |
| `stage-b-control-center` | Bluetooth, notifications, updates, clipboard, capture |
| `stage-c-power-user` | VPN, storage, processes, keybinds, app vault |
| `stage-d-polish` | idle, printers, logs, live wallpaper |
| `freebsd-ui-package` / `main` | Packaging (Debian + FreeBSD), CI, docs |

### Security posture worth preserving
The backend has **no arbitrary shell endpoint**: actions and launch targets are
allowlisted, the server binds `127.0.0.1` on a random port, and every request
must carry a per-launch `X-LMDP-Token` (plus strict `Origin`/`Host` and
`Sec-Fetch-Site` checks). This is a good contract to keep if any GUI lands here.

## 3. Theme elements to include (the "Digitalvapor" design system)

The design system is essentially the **productionized version of our mockup** —
the raw palette hexes are identical (`--dv-mag #ff2e97`, `--dv-cyan #01cdfe`,
`--dv-mint #05ffa1`, `--dv-purple #b967ff`, `--dv-bg #05060a` … match
`palette/vapor-matrix.theme` exactly). That parity makes it low-risk to adopt.

High-value theme elements to pull in:

- **Semantic token layer** — `--dv-accent`, `--dv-text`, `--dv-line`, `--dv-panel`,
  `--dv-surface`, spacing scale, type stacks. Components reference roles, not raw
  colors, so re-theming (accent pair, opacity, blur, radius, rain intensity) is a
  token swap. This is the single most reusable piece.
- **Signature effects** — matrix rain canvas, CRT scanline overlay, vignette,
  neon text/box glow, blueprint corner marks, flicker/float/pulse keyframes.
  These define the "vapor//matrix" identity far more than the palette alone.
- **Component library** — panels/cards, buttons (primary/outline/ghost/danger),
  tags, fields, toggles, sliders, tabs, progress/spinner, dropdowns, context
  menus, dialogs, toasts, window chrome, side panel + dock. Framework-free, so
  it drops into any static page.
- **Typography** — display headings in **Zen Dots**, Japanese accents in
  **DotGothic16**, body/mono in **JetBrains Mono** (all already fetched by
  `scripts/fetch-fonts.sh`), with kanji glyphs used as scene/status icons.
- **Runtime appearance → config bridge** — settings generate
  `~/.config/gtk-{3,4}.0/lmdesktopplus-generated.css` and
  `hypr-generated.conf`, so GUI appearance changes flow back into the actual
  desktop theme. This closes the loop between "the app" and "the rice".

## 4. Features to leverage (the adapters)

The control center isolates host controls behind ~18 small, **fail-soft**
adapters (each degrades to "unavailable" instead of crashing when a tool is
missing). Grouped by how directly they extend the rice:

- **Appearance / rice-adjacent (highest fit):** `wallpaper` (catalog + apply),
  `live_wallpaper` (matrix rain / mpvpaper), `keybinds` (Hyprland chord overlay
  editor), `session` (arm Hyprland from Cinnamon), generated GTK/Hyprland overlays.
- **System telemetry & control:** live CPU/mem/disk/net/temp/battery metrics with
  rolling charts, `audio`, `display` brightness, `processes`, `storage`, `logs`.
- **Connectivity:** `network` (NetworkManager Wi-Fi scan/connect), `vpn`,
  `bluetooth`.
- **Productivity / desktop glue:** quick launchers (terminal/tmux/editor/browser/
  rofi/files), `notifications` + DND, `clipboard` history, `capture` screenshots,
  `printers`, `updates`.
- **Differentiators:** agent registry with per-agent homes, workspaces, and
  optional Bubblewrap isolation; the **App Vault** (allowlisted `pkexec apt`
  installs); and a **UI Kit** scene for prototyping components before shipping.

## 5. Recommended path (options, not a commitment)

Pick a tier based on how far we want `feature/lmdesktopplus` to move toward the
`main` vision:

1. **Theme-only refresh (lowest risk).** Vendor `digitalvapor.css` tokens/effects
   as the shared source of truth and regenerate the hard-coded app configs
   (kitty/rofi/GTK) from it. Refreshes the look, keeps the project Bash-only, no
   new runtime.
2. **Static showcase.** Add the `digitalvapor.{css,js}` component kit + a static
   UI-kit/preview page (no Python backend) so the design system is documented and
   browsable — a natural upgrade of `assets/preview/`.
3. **Adopt the control center.** Bring the Python machine UI over (or promote
   `main`), starting with the rice-adjacent adapters (wallpaper, live wallpaper,
   session, keybinds, appearance→overlay bridge), then telemetry and
   connectivity. Highest payoff, largest surface; keep the loopback+token
   security contract intact.

Suggested next step: confirm the target tier, then scope the specific
adapters/scenes for a first slice.
