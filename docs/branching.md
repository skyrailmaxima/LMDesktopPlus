# Branching and review stack

Preferred base / default (until collapse): `feature/lmdesktopplus`.  
Mirror trunk after the 0.6.8 land: `main` (same tip). Post-review collapse:
[`collapse-trunk.md`](collapse-trunk.md).

## Rules

1. One concern per PR. Titles must match the files changed.
2. Hyprland PRs must not ship `src/lmdesktopplus/**` machine UI.
3. Adapter PRs must not change installer PPA policy.
4. Do not force-push shared long-lived branches; open successor PRs instead.
5. Community PPAs require explicit opt-in (`--allow-community-ppa` or
   `--hyprland-source=ppa`).
6. CI must stay green: `.github/workflows/ci.yml` runs `./tests/run-all.sh` on
   `main` and `feature/lmdesktopplus` (push + PR).

## Ready to collapse (landed)

The draft stack `#10`–`#17` is merged into `main` / `feature/lmdesktopplus`.
After human review + green CI, delete remotes with:

```bash
./scripts/collapse-stack.sh --check
CONFIRM=yes DELETE=1 ./scripts/collapse-stack.sh --delete
```

| Branch | Scope (landed) |
|---|---|
| `cursor/stage-c-power-user-081e` | **0.5.0** Stage C |
| `cursor/stage-d-polish-081e` | **0.6.0–0.6.2** Stage D |
| `cursor/deconvolute-comments-081e` | **0.6.3** `@use` / dispatch parity |
| `cursor/branchless-preopt-081e` | **0.6.4** preopt outcomes |
| `cursor/preopt-remaining-adapters-081e` | **0.6.5** remaining adapters |
| `cursor/preopt-plan-keybinds-081e` | plan for 0.6.6 (docs) |
| `cursor/preopt-keybinds-actions-agents-081e` | **0.6.6–0.6.7** + AMD GPU |
| `cursor/freebsd-ui-package-081e` | **0.6.8** FreeBSD UI package |

## Landed on trunk

| Topic | Notes |
|---|---|
| Hyprland Mint install (PR #3) | Distro packages by default; community PPA opt-in |
| Debian packaging (PR #5) | `pyproject.toml`, desktop entry, `packaging/build-deb.sh` |
| Control center (PR #8) | Loopback machine UI + Digitalvapor + Stage A/B |
| Adapter contract (PR #9) | Envelope, domain state, Origin/Host checks |
| Stage C–D + preopt + FreeBSD (`#10`–`#17`) | Through **0.6.8**; see CHANGELOG |
| VM lab | QEMU/KVM Mint guest scripts under `scripts/vm/` |
| GitHub CI | `CI` workflow → `./tests/run-all.sh` (deb + FreeBSD stage) |

## Superseded

| Branch / PR | Status |
|---|---|
| `cursor/feature-adapter-contract-17f1` | Merged via PR #9 |
| `fix/install-hyprland-on-mint` (PR #1) | Close — Hyprland successor merged |
| `cursor/stage-b-control-center-17f1` (PR #2) | Close — control center promoted via PR #8 |
| Draft stack PRs `#10`–`#17` | Closed after tip merge to trunk |

## Not split further

Separate PRs for Digitalvapor-only, Stage A-only, and Stage B-only were deferred:
`static/app.js`, `server.py`, and the frontend asset tests share one surface.
