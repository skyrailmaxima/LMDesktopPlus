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
| `cursor/stage-c-power-user-081e` | **0.5.0** Stage C complete (Tranches 1–6 + fncache use-level hashmap) |
| `cursor/stage-d-polish-081e` | **0.6.0–0.6.2** Stage D Tasks 19–23 (idle, printers, logs, live wallpaper, stow/Suggests/kit) |
| `cursor/deconvolute-comments-081e` | **0.6.3** comment/unpack + `@use`/dispatch parity across adapters |
| `cursor/branchless-preopt-081e` | **0.6.4** preopt outcomes + ternary/single-loop hot paths |
| `cursor/preopt-remaining-adapters-081e` | **0.6.5** preopt for updates/printers/logs/idle/vault/session/live_wallpaper |

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
