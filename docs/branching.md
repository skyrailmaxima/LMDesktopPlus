<<<<<<< HEAD
# Branching and PR stack

LMDesktopPlus development is split into reviewable topic branches so a
Hyprland installer change cannot block (or be blocked by) UI, packaging, or
adapter work.

## Preferred base

`feature/lmdesktopplus` — Cinnamon-first rice + shared packages.

## Topic map

```text
feature/lmdesktopplus
├── cursor/fix-hyprland-mint-install-17f1
│     Hyprland install flags, TTY launcher, session/package links, install docs
├── cursor/feature-control-center-core-17f1
│     Python loopback server, settings, telemetry, allowlisted actions
│   └── cursor/feature-digitalvapor-ui-17f1
│         Digitalvapor CSS/JS shell + intensity presets
│       └── cursor/feature-machine-adapters-stage-a-17f1
│             audio / display / session / wallpaper adapters
│           └── cursor/feature-machine-adapters-stage-b-17f1
│                 bluetooth / notifications / updates / clipboard / capture
└── cursor/feature-debian-packaging-17f1
      packaging/, pyproject packaging metadata, share/ desktop entry
```

## Rules

1. One concern per PR. Titles must match the files changed.
2. Hyprland PRs must not ship `src/lmdesktopplus/**` machine UI.
3. Adapter PRs must not change installer PPA policy.
4. Do not force-push shared long-lived branches; open successor PRs instead.
5. Community PPAs require explicit opt-in (`--allow-community-ppa` or
   `--hyprland-source=ppa`).

## Superseded work

- PR #1 (`fix/install-hyprland-on-mint`) mixed Hyprland install with the full
  machine UI and should be superseded by the Hyprland-only topic PR.
- PR #2 (`cursor/stage-b-control-center-17f1`) should be rebased onto the
  stacked adapter branches once Stage A lands as its own PR.

## Follow-up hardening (control-center / adapters)

After the topic stack exists:

- Split `/api/v1/state` into domain endpoints with independent poll intervals
- Typed adapter snapshot envelope + `error_code` values
- Cache locks, adapter exception boundaries, Host/Origin checks
- Session arm state machine (`arm_once` / `disarm` / status values)
=======
# Branching and review stack

Preferred base branch: `feature/lmdesktopplus`.

## Open review topics

| Branch | Scope | Notes |
|---|---|---|
| `cursor/fix-hyprland-mint-install-17f1` | Hyprland Mint install only | Supersedes the Hyprland portion of PR #1. Distro packages by default; community PPA requires `--allow-community-ppa`. |
| `cursor/feature-debian-packaging-17f1` | `pyproject.toml`, desktop entry, `packaging/build-deb.sh` | Lands first; no machine UI. |
| `cursor/feature-control-center-core-17f1` | Loopback machine UI + Digitalvapor + Stage A/B adapters | Stacks on packaging. Frontend/tests are coupled, so Digitalvapor and adapter stages ship together here rather than as separate PRs. |
| `cursor/feature-adapter-contract-17f1` | Envelope, domain state, locks, origin checks, session arm/disarm | Stacks on control-center. |

## Superseded / transitional

| Branch / PR | Status |
|---|---|
| `fix/install-hyprland-on-mint` (PR #1) | Mega PR; Hyprland work moved to the fix branch above. Close after the successor merges. |
| `cursor/stage-b-control-center-17f1` (PR #2) | Stage B tip on the mega history; prefer the packaging → control-center → contract stack for review. |

## Not split further (yet)

Separate PRs for Digitalvapor-only, Stage A-only, and Stage B-only were deferred:
`static/app.js`, `server.py`, and the frontend asset tests share one surface, and
extracting them without a broken intermediate tip cost more than it helped review.
>>>>>>> 70f7dce (feat: harden adapter contract with envelopes and domain state)
