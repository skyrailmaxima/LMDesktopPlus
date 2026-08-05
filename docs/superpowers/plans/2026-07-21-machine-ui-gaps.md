# Machine UI Gap Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution note:** Ship **one stage at a time**. Each stage ends with green `./tests/run-all.sh`, a version bump note in `CHANGELOG.md`, and a commit. Do not start Stage N+1 until Stage N is merged/approved.

**Goal:** Close the LMDesktopPlus machine-UI gaps (audio, display, session handoff, wallpaper, bluetooth, notifications, updates, clipboard, screenshots, then medium/minor items) with an OOP service layer, hash-mapped asset catalogs, and cheap incremental UI updates.

**Architecture:** Introduce a small set of typed **Adapter** classes (one host concern each) registered in an `AdapterRegistry` dict. The HTTP `ApplicationState` aggregates adapter snapshots into one `/api/v1/state` payload (and thin command endpoints). The frontend keeps a **scene/asset hash map** and applies **JSON Merge Patch–style diffs** so DOM work stays O(changed fields), not full re-renders every poll. Expensive host probes run on adapters with TTL caches; the UI never polls faster than `behavior.poll_interval_ms` and never rebuilds unchanged panels.

**Tech Stack:** Existing Python 3.10+ stdlib HTTP server; new adapters using `wpctl`/`pactl`, `brightnessctl`/`gdbus`, `bluetoothctl`, `nmcli`, `notify-send`/`gdbus`, MintUpdate/`apt`, `wl-clipboard`/`xclip`, `grim`/`gnome-screenshot`; Digitalvapor CSS/JS; optional SVG icons under `src/lmdesktopplus/static/icons/`.

## Global Constraints

- Loopback-only API (`127.0.0.1` / `::1`) + per-launch `X-LMDP-Token` on every mutating/state call.
- No arbitrary shell endpoint; every host command is allowlisted inside an Adapter method.
- Power / destructive actions remain behind `behavior.allow_power_actions` (or a dedicated confirm dialog).
- Prefer installed system tools; fail soft with `available: false` when binaries missing.
- OOP: one Adapter class per domain; no new god-module functions floating at package root.
- Asset lookups are `dict` / `Map` keyed by stable string IDs (never linear search of icon lists in hot paths).
- UI rendering: dirty-flag / keyed patch updates; rain canvas stays on its own rAF loop; metric charts update path data only.
- Keep Digitalvapor tokens; no Google Fonts CDN in packaged CSS.
- Target Mint (Cinnamon) + optional Hyprland; adapters must degrade cleanly on either session.
- Bump package version to **0.4.0** only after Stage A ships; later stages can be 0.4.x / 0.5.0 as noted.

---

## Design principles (apply to every stage)

### OOP layout

```text
src/lmdesktopplus/
  adapters/
    __init__.py          # AdapterRegistry + Protocol
    base.py              # Adapter base: id, available(), snapshot(), command()
    audio.py             # AudioAdapter
    display.py           # DisplayAdapter (brightness, night-light hints)
    session.py           # SessionAdapter (Hyprland/Cinnamon handoff)
    wallpaper.py         # WallpaperAdapter
    bluetooth.py         # BluetoothAdapter
    notifications.py     # NotificationsAdapter
    updates.py           # UpdatesAdapter
    clipboard.py         # ClipboardAdapter
    capture.py           # ScreenshotAdapter
    vpn.py               # VpnAdapter (Stage C)
    storage.py           # RemovableStorageAdapter (Stage C)
    processes.py         # ProcessAdapter (Stage C)
  assets.py              # AssetCatalog: hash maps for icons/scenes/actions
  server.py              # wires registry → HTTP
  static/
    icons/               # SVG map entries (see Missing assets)
    app.js               # Store + DiffRenderer + AssetMap
```

`Adapter` contract (Python):

```python
class Adapter(Protocol):
    id: str
    def available(self) -> bool: ...
    def snapshot(self) -> dict[str, Any]: ...  # cheap/cached
    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...
```

`AdapterRegistry` is a `dict[str, Adapter]` keyed by `id`. Commands route as
`POST /api/v1/adapter/{id}` → `registry[id].command(name, payload)`.

### Hash tables for assets

| Map | Key | Value | Used by |
|-----|-----|-------|---------|
| `ICON_MAP` | `"audio.volume"`, `"session.hyprland"`, … | `{svg, label, tone}` | Status strip, buttons |
| `SCENE_MAP` | scene id | `{num, jp, label, title, render}` | Dock / chips |
| `ACTION_MAP` | `"launch.terminal"`, `"session.arm_hyprland"`, … | handler metadata | Click routing |
| `CAPABILITY_MAP` | adapter id | `{available, binary, last_error}` | Settings badges |
| `WALLPAPER_MAP` | wallpaper id | `{path, thumb_path, label}` | Wallpaper picker |

Backend `assets.py` exposes `ICON_MAP` / `WALLPAPER_MAP` in `/api/v1/state` once; frontend clones into `Map` and never rebuilds unless `assets_revision` changes.

### Cheap UI rendering

1. **Split state:** `app.base` (settings, assets, capabilities — rare) vs `app.live` (metrics, audio, media — frequent).
2. **Diff poll:** server may send full snapshot; client computes shallow key diff and only patches nodes with `data-bind="live.audio.volume"`.
3. **No full `innerHTML` on live scenes** after Stage A scaffolding — use `textContent` / `style.width` / SVG `path` updates.
4. **Throttle:** charts at most 2 Hz even if poll is 1 Hz; audio slider uses local optimistic UI + debounced POST (80–120 ms).
5. **Icons:** inline SVG from `ICON_MAP` once; toggle CSS classes (`is-muted`) instead of swapping markup.
6. **Rain:** unchanged Digitalvapor canvas; intensity via dataset only.

---

## Missing assets (do not exist in package today)

Create these before or during the stage that first needs them:

| Asset path | Type | Stage | Notes |
|------------|------|-------|-------|
| `src/lmdesktopplus/static/icons/*.svg` | SVG sprites (≤1 KB each) | A | `volume`, `volume-mute`, `brightness`, `bluetooth`, `notify`, `update`, `hyprland`, `cinnamon`, `wallpaper`, `clipboard`, `camera`, `vpn`, `usb`, `power` — monochrome, `currentColor` |
| `src/lmdesktopplus/static/icons/manifest.json` | JSON hash table | A | id → filename + label; loaded once |
| `assets/wallpapers/thumbs/*.png` | 320×180 thumbs | A | Generated from `vapor-matrix.svg` (+ placeholders for user wallpapers dir) |
| `~/.local/share/lmdesktopplus/wallpapers/` | Runtime dir | A | User drops; scanned into `WALLPAPER_MAP` |
| `scripts/session-arm-hyprland.sh` | Shell | A | Thin wrapper around existing one-shot flag + instructions (or call into `switch.sh --install-only` + arm) |
| `scripts/session-hint-cinnamon.sh` | Shell | A | Prints VT hint / opens cinnamon-session docs; optional `cinnamon-session` detect |
| `docs/adapters.md` | Doc | A | Adapter contract + binary matrix |
| Optional: `share/sounds/lmdp-toast.oga` | Sound | B | Only if we add audible toast; default off |
| Optional: `packaging/depends` notes | Deb | B–C | `wireplumber`/`playerctl` already; add Suggests: `brightnessctl`, `bluez`, `grim`, `wl-clipboard` |

**Not shipping:** Google font WOFF blobs, large NeonRice HTML, live matrix wallpaper GLSL (Stage D optional).

**System binaries expected (Suggests, not hard Depends):**

| Binary | Adapter |
|--------|---------|
| `wpctl` or `pactl` | audio |
| `brightnessctl` or `gdbus` (GNOME/Cinnamon DisplayConfig) | display |
| `bluetoothctl` | bluetooth |
| `gdbus` / `notify-send` | notifications |
| `mintupdate` or `apt` | updates |
| `wl-paste`/`wl-copy` or `xclip` | clipboard |
| `grim` (+ `slurp` on Hyprland) or `gnome-screenshot` | capture |

---

## Stage map (major → minor)

| Stage | Theme | Version | Outcome |
|-------|-------|---------|---------|
| **A** | Foundation + audio + brightness + session + wallpaper | 0.4.0 | Daily machine controls feel complete |
| **B** | Bluetooth + notifications + updates + clipboard + screenshots | 0.4.1–0.4.2 | Control-center parity |
| **C** | VPN + storage + processes + agent CRUD + keybind editor + app-vault installs | 0.5.0 | Power-user depth |
| **D** | Polish: live wallpaper, printers, idle timers, logs viewer, stow | 0.5.x+ | Spec post-v1 / nice-to-have |

---

## File structure (create during Stage A unless noted)

```text
src/lmdesktopplus/adapters/{__init__,base,audio,display,session,wallpaper}.py
src/lmdesktopplus/adapters/{bluetooth,notifications,updates,clipboard,capture}.py   # Stage B
src/lmdesktopplus/adapters/{vpn,storage,processes}.py                               # Stage C
src/lmdesktopplus/assets.py
src/lmdesktopplus/static/icons/{manifest.json,*.svg}
src/lmdesktopplus/static/app.js          # refactor: Store, DiffRenderer, AssetMap
src/lmdesktopplus/static/bindings.js     # optional split if app.js > ~800 LOC
src/lmdesktopplus/server.py              # register adapters + routes
tests/python/test_adapters_audio.py …
assets/wallpapers/thumbs/
scripts/session-arm-hyprland.sh
docs/adapters.md
docs/superpowers/plans/2026-07-21-machine-ui-gaps.md   # this file
```

---

### Task 1: Adapter foundation + AssetCatalog + cheap UI store

**Files:**
- Create: `src/lmdesktopplus/adapters/base.py`, `adapters/__init__.py`, `assets.py`
- Modify: `server.py`, `static/app.js` (intro Store/Diff without changing visuals yet)
- Test: `tests/python/test_adapter_registry.py`

**Interfaces:**
- Produces: `AdapterRegistry`, `AssetCatalog.as_dict()`, `ApplicationState.adapters_snapshot()`
- Consumes: existing `ApplicationState`

- [ ] **Step 1: Write failing registry test**

```python
from lmdesktopplus.adapters import AdapterRegistry
from lmdesktopplus.adapters.base import NullAdapter

def test_registry_get_and_snapshot():
    reg = AdapterRegistry()
    reg.register(NullAdapter("probe"))
    assert "probe" in reg.as_dict()
    assert reg.get("probe").snapshot()["available"] is True
```

- [ ] **Step 2: Run test — expect FAIL (missing module)**

Run: `PYTHONPATH=src python3 -m unittest tests.python.test_adapter_registry -v`
Expected: ImportError / FAIL

- [ ] **Step 3: Implement `base.py` + `AdapterRegistry` + `NullAdapter` + `assets.py` with empty `ICON_MAP`**

- [ ] **Step 4: Wire `ApplicationState.snapshot()` to include `"assets"` and `"adapters": {}`**

- [ ] **Step 5: Add frontend `AssetMap` + `LiveStore` that keeps last snapshot and logs diff keys in dev (no UI change yet)**

- [ ] **Step 6: `./tests/run-all.sh` PASS → commit**

```bash
git add src/lmdesktopplus/adapters src/lmdesktopplus/assets.py src/lmdesktopplus/server.py src/lmdesktopplus/static/app.js tests/python/test_adapter_registry.py
git commit -m "feat: add adapter registry and asset catalog scaffolding"
```

---

### Task 2: Icon pack + manifest hash table

**Files:**
- Create: `src/lmdesktopplus/static/icons/*.svg`, `manifest.json`
- Modify: `assets.py` to load manifest once at import/startup
- Test: `tests/frontend-assets.sh` extended; `tests/python/test_assets.py`

- [ ] **Step 1: Add 12 monochrome SVGs listed in Missing assets (currentColor, 24×24 viewBox)**

- [ ] **Step 2: `manifest.json` as `{ "audio.volume": {"file":"volume.svg","label":"Volume"}, ... }`**

- [ ] **Step 3: `AssetCatalog` loads JSON into `dict`; expose via state `assets.icons`**

- [ ] **Step 4: Server static allowlist includes `icons/*` (path-safe, no `..`)**

- [ ] **Step 5: Tests + commit**

```bash
git commit -m "feat: add icon asset hash map for machine UI chrome"
```

---

### Task 3: AudioAdapter (volume / mute / default sink)

**Files:**
- Create: `adapters/audio.py`
- Modify: `server.py`, `actions.py` capabilities, Settings Display/Desktop panel, topbar status
- Test: `tests/python/test_adapters_audio.py` (mock `run_capture`)

**Host commands:** prefer `wpctl get-volume @DEFAULT_AUDIO_SINK@` / `wpctl set-volume` / `wpctl set-mute`; fallback `pactl`.

- [ ] **Step 1: Failing tests for parse helpers (`parse_wpctl_volume`)**

- [ ] **Step 2: Implement `AudioAdapter.snapshot` with 0.75s TTL cache**

- [ ] **Step 3: Commands: `set_volume` (0–100), `toggle_mute` — clamp ints; reject unknowns**

- [ ] **Step 4: UI — status strip volume % + Settings → Display slider; debounce POST 100ms; optimistic local state**

- [ ] **Step 5: Patch DOM via `data-bind="adapters.audio.volume"` width/text only**

- [ ] **Step 6: Tests + commit `feat: wire PipeWire/Pulse audio controls into machine UI`**

---

### Task 4: DisplayAdapter (brightness)

**Files:** `adapters/display.py`; Settings Display tab; optional topbar icon
**Host:** `brightnessctl g/m/s` or sysfs read-only fallback.

- [ ] **Step 1–5:** Same TDD pattern as audio (`set_brightness` 1–100, TTL cache, cheap UI bind)
- [ ] **Step 6:** Commit `feat: add display brightness adapter`

---

### Task 5: SessionAdapter (Hyprland / Cinnamon handoff)

**Files:**
- Create: `adapters/session.py`, `scripts/session-arm-hyprland.sh`
- Modify: desktop quick actions + Settings Display; reuse one-shot flag `~/.local/share/lmdesktopplus/start-hyprland-once`
- Test: unit test that `arm_hyprland` only writes the flag file (tmpdir)

**Commands:** `arm_hyprland`, `status` (detect `HYPRLAND_INSTANCE_SIGNATURE`, `XDG_CURRENT_DESKTOP`, VT hints).
**Do not** revive broken `openvt+su` launch.

- [ ] Implement + UI buttons “ARM HYPRLAND (TTY F3)” / “HYPRLAND ACTIVE” badge
- [ ] Commit `feat: session handoff controls for Hyprland one-shot arming`

---

### Task 6: WallpaperAdapter + thumbs

**Files:** `adapters/wallpaper.py`; `assets/wallpapers/thumbs/`; Settings Appearance
**Commands:** `list`, `apply` (Cinnamon `gsettings` + copy for hyprpaper PNG/SVG paths already used by installer).

- [ ] Generate thumb for `vapor-matrix.svg` via `rsvg-convert`/`convert` in repo or script `scripts/gen-wallpaper-thumbs.sh`
- [ ] Scan package wallpapers + `~/.local/share/lmdesktopplus/wallpapers/`
- [ ] `WALLPAPER_MAP` in assets; UI grid uses `<img loading="lazy">` thumbs only
- [ ] Commit `feat: wallpaper picker with thumb hash map`

---

### Task 7: Stage A integration — DiffRenderer + docs + 0.4.0

**Files:** `app.js` DiffRenderer; `docs/adapters.md`; `CHANGELOG.md`; `__init__.py` version `0.4.0`; `pyproject.toml`

- [ ] Desktop/Monitor live panels stop full `innerHTML` rebuilds when only metrics change
- [ ] `./tests/run-all.sh` green
- [ ] Commit `release: machine UI 0.4.0 stage A controls`

**Stage A exit criteria:** volume, mute, brightness, session arm, wallpaper apply, icon map, adapter registry, tests green.

---

## Stage B — Control-center parity

### Task 8: BluetoothAdapter
- `bluetoothctl` scan/connect/disconnect/power; 5s scan cache; UI under Settings → Network or new tab.
- [x] Commit `feat: bluetooth adapter`

### Task 9: NotificationsAdapter
- List recent via `gdbus` call to `org.freedesktop.Notifications` if available; `do_not_disturb` setting; `notify-send` test.
- Host notification history may be limited — document fallback “send test only”.
- [x] Commit `feat: notification bridge and DND toggle`

### Task 10: UpdatesAdapter
- Detect `mintupdate` GUI launch + `apt list --upgradable` count (cached 10 min).
- Badge on dock/settings; button opens Mint Update.
- [x] Commit `feat: pending update count and MintUpdate launcher`

### Task 11: ClipboardAdapter
- `wl-paste`/`xclip` read (+ optional history ring of last 20 in memory only, never disk).
- [x] Commit `feat: clipboard peek and copy actions`

### Task 12: ScreenshotAdapter (capture)
- Hyprland: `grim` (+ `slurp` for region); Cinnamon: `gnome-screenshot` / `spectacle` fallback.
- Save under `~/Pictures/lmdesktopplus/` ; open folder allowlisted.
- [x] Commit `feat: screenshot capture actions`
- [x] Commit `release: 0.4.2 stage B control center`

**Stage B exit criteria:** all five adapters fail-soft; UI panels exist; Suggests documented in `docs/adapters.md`.

---

## Stage C — Power-user depth

### Task 13: VpnAdapter
- NM VPN connection list/up/down via `nmcli`; no secret storage in LMDP.
- [x] Commit `feat: vpn adapter`

### Task 14: RemovableStorageAdapter
- `lsblk -J` parse + `udisksctl mount/unmount` allowlist by device node pattern.
- [x] Commit `feat: removable storage adapter`

### Task 15: ProcessAdapter
- Top-N from `/proc` (CPU% approx); `terminate` only for UID==self; confirm dialog.
- [x] Commit `feat: process list adapter`

### Task 16: Agent CRUD API
- `POST /api/v1/agents` create/update/delete with `safe_name`; UI form on Agents settings tab.
- Keep bwrap rules as-is.

### Task 17: Keybind editor (Hyprland-focused)
- Parse/write a **generated** `~/.config/lmdesktopplus/hypr-binds.conf` sourced from hyprland.conf (same ownership guard as theme overlay).
- Do not rewrite arbitrary user binds.

### Task 18: App vault → optional apt install
- Map feature toggles to package names hash table `FEATURE_PACKAGES`; `pkexec apt-get install` only when user confirms; never silent root.
- Commit `release: 0.5.0 stage C power user`

---

## Stage D — Polish / post-v1

### Task 19: Idle / lock timer settings → cinnamon-screensaver / swayidle snippets (generated files only)
**Status:** shipped in **0.6.0** (`IdleAdapter`, Display timers, owned `swayidle-generated.sh`).

### Task 20: PrintersAdapter via `lpstat` (status read-only + open `system-config-printer`)
**Status:** shipped in **0.6.0**.

### Task 21: Logs viewer — `journalctl --user -n 200` capped text panel (escape HTML)
**Status:** shipped in **0.6.0** (Monitor → USER JOURNAL panel).

### Task 22: Live matrix wallpaper (optional HTML wallpaper window or `mpvpaper`) — feature-flagged; default on
**Status:** shipped in **0.6.1** (`LiveWallpaperAdapter`, `--live-wallpaper`, owned hypr rules); default **on** in **0.6.2** (START still explicit).

### Task 23: Stow mode / packaging Suggests tidy / UI kit stories for each new control
**Status:** shipped in **0.6.2** (`docs/suggests.md`, `./stow.sh`, kit Stage C/D stories).

---

## Testing strategy (every task)

| Layer | Command |
|-------|---------|
| Unit | `PYTHONPATH=src python3 -m unittest tests.python.test_adapters_* -v` |
| Full | `./tests/run-all.sh` |
| Manual Stage A | `PYTHONPATH=src python3 -m lmdesktopplus --browser` → change volume/brightness, arm Hyprland, apply wallpaper |
| Perf check | Poll 1s: verify Monitor scene does not flicker; Performance panel / logging of diff key count < 20/tick |

Mock `util.run_capture` in adapter tests — do not require real PipeWire/Bluetooth hardware in CI.

---

## Spec coverage checklist

| Gap | Stage / Task |
|-----|----------------|
| Audio volume/mute | A / 3 |
| Brightness / real Display tab | A / 4 |
| Session Hyprland/Cinnamon handoff | A / 5 |
| Wallpaper picker | A / 6 |
| Bluetooth | B / 8 |
| Notifications / DND | B / 9 |
| Updates | B / 10 |
| Clipboard | B / 11 |
| Screenshots | B / 12 |
| VPN | C / 13 |
| USB storage | C / 14 |
| Process list | C / 15 |
| Agent CRUD | C / 16 |
| Keybind editor | C / 17 |
| App vault installs | C / 18 |
| Idle, printers, logs, live wallpaper | D / 19–22 |
| OOP adapters | A / 1 |
| Hash-mapped assets | A / 1–2, 6 |
| Cheap UI updates | A / 1, 3, 7 |

---

## Risks

| Risk | Mitigation |
|------|------------|
| `app.js` becomes unmaintainable | Split `bindings.js` / `store.js` when >800 LOC |
| Host binary maze | Capability badges + docs matrix; never throw on missing binary |
| Accidental full re-render regress | Test or assert `renderScene(false)` path uses binders for live scenes |
| Privilege installs | Stage C only; explicit confirm + `pkexec` |
| Bluetooth/notifications API fragility | Fail soft; Stage B snapshots optional |

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-21-machine-ui-gaps.md`.

**Recommended order:** Stage A (Tasks 1–7) first as one PR series → Stage B → Stage C → Stage D.

**Two execution options when ready to build:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — execute tasks in this session with checkpoints

Which approach (and confirm Stage A-only vs full A→D continuum)?
