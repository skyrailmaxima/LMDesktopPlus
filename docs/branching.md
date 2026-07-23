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
