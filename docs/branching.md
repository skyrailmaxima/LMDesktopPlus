# Branching and review stack

Preferred base branch: `feature/lmdesktopplus`.

## Rules

1. One concern per PR. Titles must match the files changed.
2. Hyprland PRs must not ship `src/lmdesktopplus/**` machine UI.
3. Adapter PRs must not change installer PPA policy.
4. Do not force-push shared long-lived branches; open successor PRs instead.
5. Community PPAs require explicit opt-in (`--allow-community-ppa` or
   `--hyprland-source=ppa`).

## In flight

| Branch | Scope |
|---|---|
| `cursor/stage-c-power-user-081e` | Stage C adapters: VPN, storage, processes (0.4.4); next: dispatch refactor then agent CRUD / keybinds / vault → 0.5.0 |
| *(planned)* `cursor/dispatch-refactor-081e` | Optional split PR: hashmap/bindings deconvolution before Tasks 16–18 |

## Landed on `feature/lmdesktopplus`

| Topic | Notes |
|---|---|
| Hyprland Mint install (PR #3) | Distro packages by default; community PPA opt-in; one-shot bashrc; `hypr-generated.conf` stub |
| Debian packaging (PR #5) | `pyproject.toml`, desktop entry, `packaging/build-deb.sh` |
| Control center (PR #8 / promoted #6) | Loopback machine UI + Digitalvapor + Stage A/B adapters |
| Adapter contract (PR #9) | Envelope, domain state, locks, Origin/Host checks, session arm/disarm |
| VM lab | QEMU/KVM Mint guest scripts under `scripts/vm/` |

## Superseded

| Branch / PR | Status |
|---|---|
| `cursor/feature-adapter-contract-17f1` | Merged via PR #9 |
| `fix/install-hyprland-on-mint` (PR #1) | Close — Hyprland successor merged |
| `cursor/stage-b-control-center-17f1` (PR #2) | Close — control center promoted via PR #8 |
| `cursor/feature-debian-packaging-17f1` tip after #6 | Control center mistakenly merged here; content promoted via PR #8 |

## Not split further

Separate PRs for Digitalvapor-only, Stage A-only, and Stage B-only were deferred:
`static/app.js`, `server.py`, and the frontend asset tests share one surface.
