# Collapse trunk after review

The 0.5.0–0.6.8 draft stack (`#10`–`#17`) is already merged into both
`feature/lmdesktopplus` and `main` (same tip). This document is the post-review
checklist so GitHub CI can gate the collapse and old stack branches can be
removed safely.

## Before you collapse

1. Review the landed tip on `main` / `feature/lmdesktopplus`.
2. Confirm **CI / test (ubuntu)** is green on that tip
   (Actions → CI workflow, or the status check on the commit).
3. Optionally set the GitHub **default branch** to `main`
   (Settings → General → Default branch). Repo default may still be
   `feature/lmdesktopplus` until you switch it.
4. Enable branch protection on `main` (recommended):
   - Require a pull request before merging (optional if you push directly)
   - Require status checks: **`test (ubuntu)`**
   - Do not allow force pushes

## Verify stack tips are in trunk

```bash
./scripts/collapse-stack.sh --check
```

This fails if any listed stack tip is not an ancestor of `main`.

## Delete remote stack branches

Dry-run (default):

```bash
./scripts/collapse-stack.sh
```

Delete (only after review + green CI):

```bash
CONFIRM=yes DELETE=1 ./scripts/collapse-stack.sh --delete
```

Branches covered: Stage C → FreeBSD UI package (`cursor/*-081e` stack from
PR `#10`–`#17`). The plan-only `preopt-plan-keybinds` tip was cherry-picked
(new SHA on trunk) and is deleted as a documented exception.

## Keep or retire `feature/lmdesktopplus`

After default is `main`:

- **Keep** `feature/lmdesktopplus` as a mirror of `main` for a short period, or
- Fast-forward it whenever `main` moves, then delete once teammates switch remotes.

Do not force-push either long-lived branch.

## Local cleanup

```bash
git fetch --prune
git checkout main
git pull origin main
git branch -d cursor/freebsd-ui-package-081e   # example; only if fully merged
```
