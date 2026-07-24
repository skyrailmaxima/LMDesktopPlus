# Dispatch Deconvolution + Stage C Connection Plan

> **For agentic workers:** Ship **one tranche at a time**. Each tranche ends with green
> `./tests/run-all.sh` and a commit. Do not start Stage C feature work (Tasks 16–18)
> until Tranche 1 lands — otherwise those features grow the same branched surfaces.

**Goal:** Deconvolute LMDesktopPlus control-flow so **hash maps / dispatch tables** are
the primary way to resolve “what runs for this key,” loops live in **named
subfunctions**, and branched `if/elif` trees are reserved for true validation /
fail-soft edges. Then connect the remaining Stage C features (agent CRUD, keybind
editor, app vault) onto those rails.

**Why now:** `app.js` is ~1466 LOC (plan threshold ~800). Stage C adapters (0.4.4)
added more `send*Command` twins and `data-*` bind clones. Tasks 16–18 will add more
settings tabs, POST routes, and click handlers — without this pass they land as more
branches.

**Architecture principles (non-negotiable for this plan):**

1. **Map first.** Scene → renderer, tab → panel, `data-*` → handler, route → handler,
   command name → method, feature id → package metadata.
2. **Extract loops.** Nested DOM/list walks become named helpers
   (`syncCoreBars`, `mapVpnRows`, …) with one job each.
3. **Branches only at the edge.** Auth failures, payload validation, missing binary —
   not for selecting among known peers.
4. **Preserve behavior.** No UX redesign; refactor + thin feature hooks only.

**Tech stack:** Existing Python stdlib server, Digitalvapor/`app.js`, unittest +
`tests/frontend-assets.sh`.

---

## Current good patterns (extend, do not reinvent)

| Location | Pattern |
|---|---|
| `app.js` `renderScene` | `renderers = { desktop: … }` map |
| `actions.py` `launch` | `handlers = { "terminal": … }` map |
| `server.py` state domains | `loaders = { "core": … }` map |
| `adapters/__init__.py` | `ADAPTER_CAPABILITIES` capability table |
| `static/icons/manifest.json` | Asset id → file hash map |

---

## Hotspot inventory (refactor targets)

| # | File | Hotspot | Preferred shape |
|---|---|---|---|
| 1 | `app.js` ~1357–1422 | `bindSceneEvents` ~35 `data-*` clones | `SCENE_BINDINGS` registry → `bindings.js` |
| 2 | `app.js` ~763–809 | `renderSettingsTab` if-chain | `SETTINGS_TABS[tab] → renderFn` |
| 3 | `server.py` POST | sequential `if path ==` | `POST_ROUTES` + adapter prefix rule |
| 4 | `server.py` GET | residual path ifs | `GET_ROUTES` / prefix table |
| 5 | `app.js` command helpers | nine `send*Command` twins | `adapterCommand(id, name, payload)` |
| 6 | adapter `command()` | per-name if-chains | `COMMANDS = {name: bound_method}` |
| 7 | `actions.py` `run` | action if/elif | `ACTION_HANDLERS` (mirror `launch`) |
| 8 | `app.js` monitor patch | nested DOM sync | `syncCoreBars` / `renderThermalRows` / `renderPowerPanel` |
| 9 | `app.js` `renderApps` | ad-hoc feature tuples | unify with `FEATURE_PACKAGES` (Task 18) |
| 10 | `audio` / `capture` | backend argv if/else | `(name, backend) → argv` tables |

---

## Stage map

| Tranche | Theme | Outcome | Version note |
|---|---|---|---|
| **1** | Frontend dispatch + split | `bindings.js` + `SETTINGS_TABS` + `adapterCommand`; `app.js` shrinks | no bump (refactor) |
| **2** | Server + action dispatch | `POST_ROUTES` / `GET_ROUTES` / `ACTION_HANDLERS` | no bump |
| **3** | Adapter command tables | shared `dispatch_command` helper; vpn/storage/processes first | no bump |
| **4** | Connect Task 17 keybinds | generated `hypr-binds.conf` on dispatch rails | 0.4.5 or fold into 0.5.0 |
| **5** | Connect Task 16 agent CRUD | `POST /api/v1/agents` + Agents tab form | toward 0.5.0 |
| **6** | Connect Task 18 app vault | `FEATURE_PACKAGES` + confirm/`pkexec` | **0.5.0** release |

Recommended order for feature connection after rails: **17 → 16 → 18**
(keybinds grow settings bindings hardest; agents need new POST routes; vault needs
the feature hash table that also cleans `renderApps`).

---

## Tranche 1 — Frontend dispatch (do first)

**Files:**
- Create: `src/lmdesktopplus/static/bindings.js`
- Modify: `src/lmdesktopplus/static/app.js`, `index.html` (script order),
  `tests/frontend-assets.sh`
- Optional extract: keep `LiveStore` / `DiffRenderer` / `AssetMap` in `app.js` for
  this tranche; only move event binding + settings tab map unless LOC still > 1000

### Task 1.1: `adapterCommand` collapse

- [x] Replace `sendAudioCommand` … `sendProcessCommand` with:

```js
async function adapterCommand(adapterId, name, payload = {}) {
  return api(`/api/v1/adapter/${adapterId}`, {
    method: "POST",
    body: { name, payload },
  });
}
```

- [x] Call sites become `adapterCommand("vpn", "up", { name })` etc.
- [x] Grep/assert in `frontend-assets.sh` for helper + at least one Stage C adapter id

### Task 1.2: `SETTINGS_TABS` map

- [x] Replace `renderSettingsTab` if-chain with:

```js
const SETTINGS_TABS = {
  appearance: renderAppearanceSettings,
  display: renderDisplaySettings,
  network: renderNetworkSettings,
  agents: renderAgentSettings,
  keybinds: renderKeybinds,
  about: renderAbout,
};
```

- [x] Extract appearance/display bodies into named functions (already partly split for network)
- [x] Unknown tab → `renderAbout` (or explicit fallback), no else ladder

### Task 1.3: `SCENE_BINDINGS` + extract loops

- [x] Introduce registry:

```js
// bindings.js
const SCENE_BINDINGS = [
  { sel: "[data-launch]", type: "click", run: (el) => runAction("launch", el.dataset.launch) },
  { sel: "[data-vpn-name]", type: "click", run: (el) => vpnAction(el.dataset.vpnAction, el.dataset.vpnName) },
  // …
];

function bindSceneEvents(root) {
  for (const { sel, type, run } of SCENE_BINDINGS) {
    $$(sel, root).forEach((el) => el.addEventListener(type, () => run(el)));
  }
}
```

- [x] Split row builders out of panels:
  - `mapVpnConnectionRows(connections)`
  - `mapStorageDeviceRows(devices)`
  - `mapProcessRows(processes)`
  - `syncCoreBars(root, cores)` / `renderThermalRows` / `renderPowerPanel` from
    `patchMonitorCollections`
- [x] Load `bindings.js` before `app.js` in `index.html` (same CSP `script-src 'self'`)
- [x] `node --check` both files; `./tests/run-all.sh`
- [ ] Commit: `refactor: dispatch tables and bindings.js for machine UI events`

**Exit criteria:** No new `if (app.settingsTab === …)` chain; `bindSceneEvents` is a
loop over a table; Stage C UI behavior unchanged.

---

## Tranche 2 — Server and actions dispatch

**Files:** `server.py`, `actions.py`, `tests/python/test_server.py`

### Task 2.1: POST/GET route tables

- [ ] Shape:

```python
POST_ROUTES: dict[str, Callable] = {
    "/api/v1/settings": handle_settings,
    "/api/v1/action": handle_action,
    "/api/v1/agents/launch": handle_agents_launch,
    "/api/v1/media": handle_media,
    "/api/v1/network/connect": handle_network_connect,
    "/api/v1/network/disconnect": handle_network_disconnect,
}
# Prefix rule (not a branch ladder):
# if path.startswith("/api/v1/adapter/"): handle_adapter(path, body)
```

- [ ] Mirror for GET: exact paths + `startswith` prefix map for thumbs/static
- [ ] Keep auth/body parsing outside the dispatch (single gate)
- [ ] Tests still cover Origin/Host, adapter errors, domain state

### Task 2.2: `ACTION_HANDLERS` for `ActionRunner.run`

- [ ] Same style as existing `launch` handlers map
- [ ] Extract shared `wrap_in_terminal(argv, *, cwd=None, hold=False)` to kill
      duplicated kitty/gnome-terminal argv branches where safe

**Exit criteria:** Adding Task 16’s `POST /api/v1/agents` is one map entry, not a new
`if` block in the middle of `do_POST`.

---

## Tranche 3 — Adapter command dispatch helper

**Files:** `adapters/base.py`, then `vpn.py` / `storage.py` / `processes.py` (newest),
optionally bluetooth/clipboard/capture

### Task 3.1: shared helper

```python
def dispatch_command(
    commands: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    handler = commands.get(name)
    if handler is None:
        return command_error("unavailable", f"unknown command: {name}")
    return handler(payload)
```

- [ ] Each adapter exposes `COMMANDS` property or module-level table bound in
      `__init__` / `command()`
- [ ] Unit tests keep mocking `run_capture`; only wiring changes
- [ ] Commit: `refactor: hashmap command dispatch for stage C adapters`

**Defer:** full audio/capture argv matrix unless a touch is required — consistency
nice-to-have, not blocking Tasks 16–18.

---

## Tranche 4 — Connect Task 17: Keybind editor

**Depends on:** Tranche 1 (`SETTINGS_TABS`, `SCENE_BINDINGS`) + Tranche 2 (POST route)

**Files:** new adapter or small `keybinds.py` service; generated
`~/.config/lmdesktopplus/hypr-binds.conf`; Settings → Keybinds UI; tests

- [ ] Parse/write **only** LMDP-owned bind file (ownership guard like theme overlay)
- [ ] UI: list rows from a `DEFAULT_BINDS` hash map (combo → action id), edit via
      form controls bound through `SCENE_BINDINGS`
- [ ] Commands via map: `list` / `set` / `reset` — no free-form shell
- [ ] Do not rewrite arbitrary user `hyprland.conf` binds
- [ ] Commit: `feat: generated Hyprland keybind editor`

---

## Tranche 5 — Connect Task 16: Agent CRUD API

**Depends on:** Tranche 2 route table; Tranche 1 Agents tab bindings

**Files:** `agents.py`, `server.py` POST map entry, Agents settings UI, tests

- [ ] `POST /api/v1/agents` with `op` ∈ `{create, update, delete}` **or** separate
      paths registered in `POST_ROUTES` — prefer one path + `op` map inside handler
- [ ] `safe_name` validation; refuse command arrays that escape allowlisted patterns
      already used by registry
- [ ] UI form fields → PATCH-like payload; spawn button stays on existing launch route
- [ ] Keep bwrap rules as-is
- [ ] Commit: `feat: agent CRUD API and settings form`

---

## Tranche 6 — Connect Task 18: App vault installs + 0.5.0

**Depends on:** Tranche 1 feature row helpers; confirm dialog pattern

**Files:** `FEATURE_PACKAGES` map (Python + mirrored UI ids), `renderApps`, packaging
Suggests notes, tests

```python
FEATURE_PACKAGES = {
    "hyprland": {"apt": ["hyprland"], "label": "Hyprland session"},
    "bluetooth": {"apt": ["bluez"], "label": "Bluetooth tools"},
    # …
}
```

- [ ] Unify `renderApps` entries with this map (capabilities + install affordance)
- [ ] Install only via explicit confirm + `pkexec apt-get install`; never silent root
- [ ] Fail soft when `pkexec`/apt missing
- [ ] `CHANGELOG` + version **0.5.0**; README Stage C complete note
- [ ] Commit: `release: 0.5.0 stage C power user`

---

## Testing strategy

| Layer | Command |
|---|---|
| Unit | `PYTHONPATH=src python3 -m unittest discover -s tests/python -v` |
| Frontend syntax | `node --check src/lmdesktopplus/static/{digitalvapor,bindings,app}.js` |
| Full | `./tests/run-all.sh` |
| Refactor guard | Manual smoke: Settings tabs, VPN/storage/process controls still fire |
| Perf | Monitor scene: metrics still patch without full rebuild unless processes change |

---

## Risks

| Risk | Mitigation |
|---|---|
| `bindings.js` breaks CSP / load order | Script tags `digitalvapor.js` → `bindings.js` → `app.js`; keep `script-src 'self'` |
| Route table misses adapter prefix | Explicit prefix handler registered beside exact map; test adapter + 404 |
| Behavior drift in settings tabs | Screenshot-free: assert tab render functions still emit known `data-*` hooks in `frontend-assets.sh` |
| Agent CRUD opens command injection | Reuse `safe_name` + existing command allowlisting; no arbitrary argv from UI |
| `pkexec` UX surprise | Confirm dialog copy; default features remain toggles-only until confirm |

---

## Out of scope

- Visual redesign / Digitalvapor token changes
- Stage D (idle, printers, logs, live wallpaper)
- Rewriting Stage A/B adapters’ host integrations beyond command dispatch tables
- Merging or force-pushing `feature/lmdesktopplus`

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-24-dispatch-refactor-stage-c.md`.

**Next concrete step:** Tranche 1 Task 1.1–1.3 on `cursor/stage-c-power-user-081e`
(or a successor `cursor/dispatch-refactor-081e` if PR #10 should stay adapter-only).

**Two execution options when ready to build:**

1. **Inline** — implement Tranche 1 in this branch/session with checkpoints
2. **Split PR** — open `cursor/dispatch-refactor-081e` off `feature/lmdesktopplus`
   (or off #10) so adapter review stays separate from the structural pass
