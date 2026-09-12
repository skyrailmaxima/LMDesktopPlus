# Draft PR stack: review, scan, and consolidation plan

Status: proposal for sign-off. This documents the review and scan of the open
draft PR stack and proposes how to consolidate it into a shallower, reviewable
stack before merge. The concrete bug fixes surfaced by the scan are already
implemented in the PR that carries this document.

## 1. Review — current stack inventory

The work is delivered as a deep linear stack of draft PRs, each based on the
previous one (ultimately on `feature/lmdesktopplus`). Cumulatively the stack is
**+4,687 / −166 across 66 files** relative to trunk (`origin/main`), and is
**0 commits behind** trunk (no divergence to reconcile).

| PR | Phase | Scope | Size |
|----|-------|-------|------|
| #21 | 0 | Promote control-center stack (v0.6.9) to integration base | 14 files, +639 |
| #22 | 1 | Native UI shell — window identity + lifecycle, single-instance | 17 files, +720 |
| #23 | 2 | VM sandbox — Xvfb screenshot smoke + Mint UI guest iteration | 8 files, +379 |
| #24 | 3 | Frontend/UX polish — store split, reduced-motion, a11y, empty states, responsive | 11 files, +381/−111 |
| #25 | 4 | Software manifest + Debian metapackage + FreeBSD metaport | 11 files, +669 |
| #26 | 5 | Scripted Linux Mint respin (live-build) | 8 files, +395 |
| #27 | 6 | Scripted FreeBSD install image (poudriere) | 12 files, +449 |
| #28 | 7 | Release + CI stages (gated ISO/image builds, tag release) | 4 files, +280 |
| #29 | A | UI feature-parity audit + prioritized backlog | 1 file, +125 |
| #30 | B | Editable greetings + per-scene title/subtitle overrides | 6 files, +445/−15 |
| #31 | C+D | Tile framework + Desktop/Monitor rollout (view modes, reorder, hide) | 10 files, +598/−39 |

Plan PRs `#19` (interface design review) and `#20` (native UI + VM sandbox plan)
target `feature/lmdesktopplus` directly and are documentation/planning only.

Assessment: the phases are individually coherent and the stack applies cleanly,
but 11 stacked implementation PRs is a lot of surface to review serially, and
several phases are tightly themed (all-frontend, all-packaging, all-distribution)
and could be reviewed together.

## 2. Scan — bug + security findings

Two scans were run over the cumulative stack (`cursor/tileable-scenes-dbff` vs
`origin/main`).

### Security review: no medium/high/critical findings
The loopback + per-launch `X-LMDP-Token` + Origin/Host contract, the
settings/customization POST validation, subprocess usage (argv lists, no
`shell=True`), the static-file allowlist, single-instance `flock`, and CI
permissions were all reviewed and found sound under the product threat model
(same-user, loopback-only). Optional defense-in-depth ideas (token on static
GET, disable WebKit devtools in production builds, non-root FreeBSD console) are
noted but are product decisions, not vulnerabilities.

### Bugbot: two real bugs — both fixed in this PR
1. **High — Mint ISO build unsatisfiable dependency.** The
   `lmdesktopplus-desktop` metapackage hard-`Depends` on Mint-only `mintupdate`,
   but `build-iso.sh` bootstraps live-build against the Ubuntu `noble` archive,
   so `lb build` cannot resolve it and the respin fails. Fixed by adding an
   optional manifest `archive` marker; archive-pinned peers become metapackage
   `Recommends` (still pulled on a real Mint install) instead of hard `Depends`.
   (`packaging/manifest.py`, `packaging/software-manifest.json`,
   `packaging/build-deb-metapackage.sh`, `tests/python/test_software_manifest.py`)
2. **Medium — tile layout save race.** Reorder/hide/view edits read the layout
   from the last server snapshot and POST asynchronously; rapid clicks (and the
   1s poll) could overwrite earlier edits because the layout arrays are replaced
   wholesale. Fixed with an optimistic in-memory draft that is authoritative
   while editing plus serialized POSTs. (`src/lmdesktopplus/static/app.js`)

A separate, earlier end-to-end verification also caught and fixed a
`ReferenceError` (`GREETING_MODES`) that blanked the Personalize tab (already in
#31).

## 3. Consolidation — proposed reviewable stack

Collapse the 11 implementation PRs into **4 themed PRs** plus this review-fixes
PR, preserving the same cumulative diff and dependency order:

| New PR | Consolidates | Theme |
|--------|-------------|-------|
| C1 — Runtime shell & dev sandbox | Phases 0, 1, 2 | integration base, native window lifecycle + single-instance, Xvfb screenshot harness |
| C2 — Frontend & editability | Phases 3, A, B, C, D | UX polish + a11y, parity audit, editable text, tile framework |
| C3 — Packaging & distribution | Phases 4, 5, 6 | software manifest/metapackage/metaport, Mint respin ISO, FreeBSD image |
| C4 — Release & CI | Phase 7 | CI workflow, gated image builds, tag release, artifact hosting |
| C5 — Review + scan fixes | this PR | Bugbot fixes + this plan |

Notes:
- The grouping keeps a clean linear order `C1 → C2 → C3 → C4` (runtime →
  frontend → packaging → release), matching real dependencies: packaging (C3)
  depends on the shell (C1); CI (C4) builds the packages (C3).
- Consolidation is done by creating **new** squashed branches from the existing
  commits (no force-push of the existing branches, no history rewrite of shared
  refs). The existing `#21–#31` are then closed in favor of `C1–C4`.
- `./tests/run-all.sh` must stay green at each new boundary (it does today).

## 4. Recommended next steps
1. Merge/land the review-fixes (this PR) so the scanned bugs are fixed.
2. On sign-off of the grouping above, create the consolidated `C1–C4` branches
   and PRs, verifying `run-all.sh` green at each.
3. Review `C1–C4` in order, then merge down into `feature/lmdesktopplus`.

Because consolidation restructures the whole stack, it is proposed here for
review first rather than executed automatically.
