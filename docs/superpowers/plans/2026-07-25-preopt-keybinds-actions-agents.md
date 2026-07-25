# Preopt — keybinds / actions / agents + file I/O (0.6.6)

> **For agentic workers:** Execute task-by-task. Each task ends green
> `./tests/run-all.sh`, a `CHANGELOG.md` note, and a commit. Do not start the
> next task until the current one is green.
>
> **Stack:** branch from `cursor/preopt-remaining-adapters-081e` (0.6.5 tip).
> Suggested branch: `cursor/preopt-keybinds-actions-agents-081e`.
> Preferred eventual base: `feature/lmdesktopplus` (via the open 0.6.3–0.6.5 stack).

## Goal

Close the remaining exception-style host edges and dense control-flow that
still sit outside the 0.6.4–0.6.5 adapter preopt pass:

1. **keybinds / actions / agents** — `run_capture` leftovers, multi-loop etch,
   terminal-wrapper drift
2. **True file I/O edges** — apply/synth paths that still let `OSError` escape
   into command responses (and, where relevant, poll)
3. **Non-adapter poll hosts** (same release if capacity allows) —
   `network.current`, `media.status`, `system_info._gpu` — these are *hotter*
   than keybinds snapshot I/O because they sit **outside**
   `AdapterRegistry.as_dict`’s exception fence

## Already done (do not redo)

| Release | Scope |
|---|---|
| **0.6.4** | `preopt` module + audio/display/processes/vpn/storage/clipboard/capture/bluetooth/notifications/wallpaper/envelope |
| **0.6.5** | updates/printers/logs/idle/vault/session/live_wallpaper |

Stage B–D **adapters** are complete for preopt. This plan is the next layer.

## Design rules (carry forward)

- Prefer `try_run` / `Outcome` / `first_ok_scan` over `except TimeoutExpired`.
- Ternary / map-first gates; **≤1 loop per subfunction**.
- Annotate with `@use` / `register_fn` on new helpers.
- Tests mock `lmdesktopplus.preopt.run_capture` (not module-local `run_capture`).
- **Do not regress:**
  - Hypr `source=` only when config already contains `LMDesktopPlus`
  - Chord vapor may override **combo only** (never dispatch)
  - Agent argv deny-list (`pkexec`, shells, paths, metacharacters)
  - Vault packages only from `FEATURE_PACKAGES` (out of scope here)
  - Loopback + token + Origin/Host unchanged

## Hot vs cold (remaining)

| Path | Temp | Why |
|---|---|---|
| `network.current` | **HOT** | Every core snapshot; no adapter fence |
| `media.status` | **HOT** | Every core snapshot (1.5s TTL) |
| `system_info._gpu` nvidia | **HOT** | Every metrics sample |
| `agents.scan_peers` / `list` | **HOT** | `executable()` only today — density, not raises |
| `keybinds.snapshot` | HOT | Already soft on hypr read; pulse is cold |
| `keybinds._pulse_hyprland` | COLD | Direct `run_capture`; **misses `TimeoutExpired`** |
| `actions.lock` | COLD | Loop of `run_capture` with **no try** |
| `actions.open_path` / `open-config` | COLD | `mkdir` can escape via `run()` |
| `theme.apply` reload | COLD | `run_capture` uncaught |
| `keybinds._atomic_write_text` | COLD | mkdir/write/replace uncaught |
| `idle` / `live_wallpaper` etch writes | COLD | mkdir/write_text uncaught (chmod soft) |
| `agents.save` / `ensure_directories` / spawn mkdir | COLD / startup | `atomic_write_json` / mkdir raise |

---

## Tranche A — Poll host edges (P0) → 0.6.6a or same PR first commits

> Highest reviewer value: stops timeouts escaping `/api/v1/state`.

### Task A1: `network.current` → `try_run`

- [ ] Replace `run_capture` in `network.current` with `try_run`
- [ ] Fail soft → empty / `available: false` shape (preserve today’s parse contract)
- [ ] Keep one parse loop in `_split_nmcli` / connection row builder
- [ ] Retarget / add mocks in `tests/python/test_network.py` → `preopt.run_capture`
- [ ] Optionally convert `scan_wifi` / `connect_wifi` / `disconnect` in the same
      commit (cold, but same module choke point)

### Task A2: `media.status` (+ `control`) → `try_run`

- [ ] `status` probe via `try_run`; missing playerctl / timeout → soft empty
- [ ] `control` via `try_run`; do not re-raise into action handler
- [ ] Add `tests/python/test_media.py` (module currently under-tested)

### Task A3: `system_info._gpu` nvidia path → `try_run`

- [ ] Wrap `nvidia-smi` in `try_run`; keep `/proc`/`sysfs` soft `OSError` as-is
- [ ] Extend `tests/python/test_system_info.py` with a mocked nvidia outcome

**Exit criteria:** Killing / delaying `nmcli` / `playerctl` / `nvidia-smi` cannot
500 the state poll.

---

## Tranche B — keybinds / actions / theme command hosts (P0)

### Task B1: `keybinds._pulse_hyprland` → `try_run`

- [ ] Drop direct `run_capture`; return soft bool / ignore reload failure
- [ ] Catch-equivalent for timeout (today’s gap)
- [ ] Retarget `tests/python/test_adapters_keybinds.py` pulse patches to
      `lmdesktopplus.preopt.run_capture`
- [ ] Add timeout soft-fail unit case

### Task B2: `actions.lock` → `first_ok_scan` + `try_run`

- [ ] Build ordered argv candidates (loginctl / cinnamon-screensaver / …)
- [ ] One-loop `first_ok_scan` probe; no bare `run_capture`
- [ ] Retarget `tests/python/test_actions.py`; cover timeout + all-fail soft

### Task B3: `theme.apply` hyprctl reload → `try_run`

- [ ] Isolate `_reload_hyprland() -> RunOutcome`
- [ ] Keep ownership write guards; only soft-fail the reload edge
- [ ] Add minimal theme reload test (new or under existing theme coverage)

### Task B4: `actions.open_path` fail-soft

- [ ] Wrap `mkdir` + `spawn` so `open-config` via `run()` never raises
- [ ] Return `command_error`-shaped `{ok:false, error}` consistent with launch

**Exit criteria:** Lock / hypr reload / open-config never surface
`TimeoutExpired` / uncaught `OSError` to the HTTP layer.

---

## Tranche C — True file I/O edges (P1)

> Soften **apply/synth** writes the way session arm/disarm already does
> (`OSError` → `command_error`). Do **not** invent foreign hypr files.

### Task C1: keybinds atomic write → Outcome

- [ ] `_atomic_write_text` → `Outcome` / bool (mkdir + write + replace)
- [ ] `_synth_matrix` / tune / melt map write failure → `command_error`
- [ ] Preserve chmod soft-fail; preserve matrix source ownership guard

### Task C2: idle + live_wallpaper etch writes

- [ ] `_apply_idle` / `_start`: wrap `mkdir` + `write_text` → `command_error`
- [ ] Keep chmod / pid kill soft
- [ ] Ownership: live wallpaper `source=` append still requires `LMDesktopPlus`

### Task C3: agents directory + roster persistence

- [ ] `ensure_directories` per-peer soft (`Outcome` / skip + warn field)
- [ ] `save()` / forge/retune/melt: map `atomic_write_json` OSError →
      `command_error` (do not crash CRUD)
- [ ] Startup `__init__` save: fail soft into empty roster + `last_error`
      rather than aborting process boot

### Task C4 (optional same PR): `util.atomic_write_json` Outcome helper

- [ ] If ≥3 call sites need the same soft write, add
      `preopt.try_atomic_write(path, text) -> Outcome` (or util twin)
- [ ] Keep chmod best-effort; document that replace remains the atomic step

**Exit criteria:** Synth chord / apply idle / start live wallpaper / forge peer
return structured errors on EACCES/ENOSPC; no traceback in server log from
those paths.

---

## Tranche D — Density / shared builds (P1–P2)

### Task D1: Share terminal wrap between `actions` and `agents`

- [ ] `agents.spawn_peer` reuses `actions.wrap_in_terminal` (or extract
      `terminal.etch_hold_argv` both consume)
- [ ] One map of terminal → argv template; no duplicated if/elif chains
- [ ] Update `tests/python/test_agents.py` + `test_actions.py` if import moves

### Task D2: keybinds etch allowlist helper

- [ ] Extract `dispatch_allowed(dispatch) -> bool` so `etch_matrix_binds`
      keeps **one** loop (drop inner `any(prefix…)`)
- [ ] Golden etch test still passes header + bind lines

### Task D3: bubblewrap bind helpers

- [ ] Split `etch_bubblewrap_argv` into:
      - `append_existing_binds(argv, paths, *, mode)` — **one loop**
      - network / unshare gate (ternary)
- [ ] Preserve bind order and `--unshare-net` gating
- [ ] No change to deny-list / etch security surface

### Task D4: agents patch map clarity (light)

- [ ] Keep `_apply_peer_patch` as one-loop patcher table (already close)
- [ ] Comment `@use` on forge/retune/melt if missing parity

**Exit criteria:** No function in keybinds/actions/agents host/etch path has
more than one loop; terminal argv templates have a single source of truth.

---

## Testing matrix

| Layer | Command |
|---|---|
| Unit focus | `PYTHONPATH=src python3 -m unittest tests.python.test_adapters_keybinds tests.python.test_actions tests.python.test_agents tests.python.test_network tests.python.test_system_info -v` |
| New | `tests.python.test_media` (Task A2) |
| Full | `./tests/run-all.sh` |
| Manual | Lock screen, synth a chord + hypr reload, forge a peer, apply idle, start live wallpaper with a read-only config dir (expect soft error) |

## Version / docs

- Bump to **0.6.6** in `__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`
- Add row to `docs/branching.md` for `cursor/preopt-keybinds-actions-agents-081e`
- PR stacked on `cursor/preopt-remaining-adapters-081e` (or rebased stack tip)

## Suggested PR shape

**One PR (preferred if stack stays draft):** Tranche A→D as sequential commits
on `cursor/preopt-keybinds-actions-agents-081e`.

**Split if review load is high:**

| PR | Scope |
|---|---|
| 0.6.6a | Tranche A (poll: network/media/gpu) |
| 0.6.6b | Tranche B + C (keybinds/actions/theme + file I/O) |
| 0.6.6c | Tranche D (density / shared terminal / bwrap) |

## Risks

| Risk | Mitigation |
|---|---|
| Accidental hypr `source=` into foreign conf | Keep `LMDesktopPlus` marker checks; tests for ownership guard |
| Chord vapor injects dispatch | Etch still matrix-owned; vapor combo-only |
| Agent elevated binaries | Deny-list unchanged; no `pkexec` in peer argv |
| Soft I/O hides real bugs | Return `last_error` / `command_error` with path hint; log once |
| Poll shape drift | Golden assert keys on network/media/metrics snapshots |

## Out of scope

- Frontend `app.js` split (`bindings.js` / `store.js`) — separate maintainability PR
- New Stage E product features
- Changing live wallpaper default or START semantics
- Widening Origin/Host or token rules

---

## Execution handoff

**Recommended order:** A1 → A2 → A3 → B1 → B2 → B3 → B4 → C1 → C2 → C3 → D1 → D2 → D3.

**First concrete step when implementing:** create
`cursor/preopt-keybinds-actions-agents-081e` from the 0.6.5 tip and land
Task A1 (`network.current` → `try_run`) with green `./tests/run-all.sh`.
