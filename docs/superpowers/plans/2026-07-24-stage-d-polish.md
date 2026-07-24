# Stage D — Polish / post-v1

> Branch: `cursor/stage-d-polish-081e` (from Stage C tip / 0.5.0).  
> Gaps source: `2026-07-21-machine-ui-gaps.md` Tasks 19–23.

## Goal

Ship post-v1 polish adapters on the existing dispatch rails (`SETTINGS_TABS`,
`SCENE_BINDINGS`, `dispatch_command`, `fncache` use levels) without opening
arbitrary shell or rewriting foreign desktop configs.

## Tranche map

| Task | Deliverable | Version |
|---|---|---|
| **19** | Idle / lock timers → owned generated snippets + Cinnamon gsettings | **0.6.0 done** |
| **20** | `PrintersAdapter` (`lpstat` read-only + open printer UI) | **0.6.0 done** |
| **21** | Logs viewer (`journalctl --user -n 200`, escaped panel) | **0.6.0 done** |
| **22** | Live matrix wallpaper (feature-flagged, default off) | **0.6.1 done** |
| **23** | Stow / Suggests tidy / UI kit stories | later |

## Task 19 — Idle

| Path | Role |
|---|---|
| `~/.config/lmdesktopplus/swayidle-generated.sh` | Owned executable swayidle launcher |
| `~/.config/lmdesktopplus/idle-generated.conf` | Human-readable note of applied timers |
| Cinnamon | `gsettings` idle-delay / screensaver lock (session only) |

Settings (`behavior`):

- `idle_lock_minutes` (0–120, 0 = off)
- `idle_sleep_minutes` (0–240, 0 = off)

Commands: `apply`, `status` via `IdleAdapter` (`id = idle`).

## Task 20 — Printers

- Snapshot: `lpstat -p -d` parsed rows + default printer
- Commands: `refresh`, `open` (`system-config-printer` or `xdg-open`)
- UI: Display settings panel

## Task 21 — Logs

- Snapshot: last ≤200 user journal lines, char-capped, control chars stripped
- Command: `refresh`
- UI: Monitor scene panel under processes; HTML escaped with existing `esc()`

## Task 22 — Live wallpaper

- Flag: `features.live_wallpaper` default **false**
- Primary backend: packaged `live-wallpaper.html` + `digitalvapor.js` rain via
  `lmdesktopplus --live-wallpaper`
- Optional: `mpvpaper` + `~/.local/share/lmdesktopplus/wallpapers/live-matrix.mp4`
- Owned: `hypr-live-wallpaper.conf`, `live-wallpaper-generated.sh`, pid file
- UI: Settings → Appearance

## Non-goals

- Task 23 in this tranche
- Editing foreign swayidle/hyprland configs without LMDesktopPlus ownership markers
- Root journal access or unbounded log pulls
- Shipping a large loop video for mpvpaper
