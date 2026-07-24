# Stage D — Polish / post-v1

> Branch: `cursor/stage-d-polish-081e` (from Stage C tip / 0.5.0).  
> Gaps source: `2026-07-21-machine-ui-gaps.md` Tasks 19–23.

## Goal

Ship post-v1 polish adapters on the existing dispatch rails (`SETTINGS_TABS`,
`SCENE_BINDINGS`, `dispatch_command`, `fncache` use levels) without opening
arbitrary shell or editing foreign configs.

## Status

| Task | Summary | Release |
|---|---|---|
| **19** | Idle / lock timers → owned generated snippets + Cinnamon gsettings | **0.6.0 done** |
| **20** | `PrintersAdapter` (`lpstat` read-only + open printer UI) | **0.6.0 done** |
| **21** | Logs viewer (`journalctl --user -n 200`, escaped panel) | **0.6.0 done** |
| **22** | Live matrix wallpaper (feature-flagged, default **on**) | **0.6.1** + default-on in **0.6.2** |
| **23** | Stow / Suggests tidy / UI kit stories | **0.6.2 done** |

## Task 19 — Idle

| Path | Role |
|---|---|
| `adapters/idle.py` | Owned swayidle script + idle-generated.conf; Cinnamon gsettings |
| Settings → Display | Lock / sleep minute sliders + APPLY IDLE SNIPPETS |

## Task 20 — Printers

- Snapshot: `lpstat -p -d` printer list
- Commands: `refresh`, `open` (`system-config-printer` or `xdg-open`)
- UI: Display settings panel

## Task 21 — Logs

- Snapshot: last ≤200 user journal lines, char-capped, control chars stripped
- Command: `refresh`
- UI: Monitor scene panel under processes; HTML escaped with existing `esc()`

## Task 22 — Live wallpaper

- Flag: `features.live_wallpaper` default **true** (START still explicit)
- Primary backend: packaged `live-wallpaper.html` + `digitalvapor.js` rain via
  `lmdesktopplus --live-wallpaper`
- Optional: `mpvpaper` + `~/.local/share/lmdesktopplus/wallpapers/live-matrix.mp4`
- Owned: `hypr-live-wallpaper.conf`, `live-wallpaper-generated.sh`, pid file
- UI: Settings → Appearance

## Task 23 — Stow / Suggests / UI kit

- `docs/suggests.md` — Suggest → adapter map (packaging truth: `build-deb.sh`)
- `./stow.sh` — optional GNU stow frontend (`--materialize-only` for CI);
  `./install.sh` remains primary
- Digitalvapor kit: Stage C/D stories (idle, printers, logs, live wallpaper,
  vault, chords, peers, vpn/storage/procs)
- Smoke: `tests/stow-mode.sh`

## Non-goals

- Editing foreign swayidle/hyprland configs without LMDesktopPlus ownership markers
- Root journal access or unbounded log pulls
- Shipping a large loop video for mpvpaper
- Replacing `install.sh` with stow-first installs
