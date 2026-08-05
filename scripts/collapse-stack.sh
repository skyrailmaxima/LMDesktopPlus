#!/usr/bin/env bash
# List (default) or delete (DELETE=1) remote stack branches after trunk collapse.
# Safe by default: prints the plan and exits 0 unless --check fails.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DELETE="${DELETE:-0}"
REMOTE="${REMOTE:-origin}"
TRUNK="${TRUNK:-main}"

# Stack branches landed via 0.5.0–0.6.8 merge (PR #10–#17). Keep tip until you
# confirm review, then delete with DELETE=1.
STACK_BRANCHES=(
  cursor/stage-c-power-user-081e
  cursor/stage-d-polish-081e
  cursor/deconvolute-comments-081e
  cursor/branchless-preopt-081e
  cursor/preopt-remaining-adapters-081e
  cursor/preopt-keybinds-actions-agents-081e
  cursor/freebsd-ui-package-081e
)

# Plan-only tip was cherry-picked onto the FreeBSD branch (new SHA); content is
# on trunk but the remote tip is not an ancestor. Safe to delete after review.
CHERRY_PICKED_BRANCHES=(
  cursor/preopt-plan-keybinds-081e
)

usage() {
  cat <<'EOF'
Usage: ./scripts/collapse-stack.sh [--check] [--delete]

  (default)   List stack branches and whether each is contained in TRUNK.
  --check     Exit 1 if any listed branch tip is not an ancestor of TRUNK.
  --delete    Delete remote stack branches (requires CONFIRM=yes).

Env:
  TRUNK=main          Trunk ref to compare against (default: main)
  REMOTE=origin       Git remote
  DELETE=1            Same as --delete
  CONFIRM=yes         Required with --delete
EOF
}

MODE=list
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    --check) MODE=check ;;
    --delete) MODE=delete; DELETE=1 ;;
    *) echo "unknown arg: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

git fetch "$REMOTE" "$TRUNK" --quiet 2>/dev/null || true
if ! git rev-parse --verify -q "$REMOTE/$TRUNK" >/dev/null; then
  echo "collapse-stack: $REMOTE/$TRUNK unavailable (fetch failed or missing); skipping" >&2
  if [[ "$MODE" == "check" || "$DELETE" == "1" ]]; then
    exit 1
  fi
  exit 0
fi
trunk_sha="$(git rev-parse "$REMOTE/$TRUNK")"
printf 'trunk %s/%s = %s\n' "$REMOTE" "$TRUNK" "$(git rev-parse --short "$trunk_sha")"

missing=0
unmerged=0
report_branch() {
  local branch="$1"
  local tag="$2"
  if ! git rev-parse --verify -q "$REMOTE/$branch" >/dev/null; then
    printf '  %-48s  (absent on %s)\n' "$branch" "$REMOTE"
    missing=$((missing + 1))
    return 0
  fi
  local tip short
  tip="$(git rev-parse "$REMOTE/$branch")"
  short="$(git rev-parse --short "$tip")"
  if git merge-base --is-ancestor "$tip" "$trunk_sha"; then
    printf '  %-48s  %s  contained-in-%s%s\n' "$branch" "$short" "$TRUNK" "$tag"
    return 0
  fi
  printf '  %-48s  %s  NOT-in-%s%s\n' "$branch" "$short" "$TRUNK" "$tag"
  if [[ "$tag" != "  [cherry-picked]" ]]; then
    unmerged=$((unmerged + 1))
  fi
}

for branch in "${STACK_BRANCHES[@]}"; do
  report_branch "$branch" ""
done
for branch in "${CHERRY_PICKED_BRANCHES[@]}"; do
  report_branch "$branch" "  [cherry-picked]"
done

if [[ "$MODE" == "check" ]]; then
  if [[ "$unmerged" -ne 0 ]]; then
    echo "collapse check failed: $unmerged branch tip(s) not in $TRUNK" >&2
    exit 1
  fi
  echo "collapse check OK ($missing absent, 0 unmerged; cherry-picked tips allowed)"
  exit 0
fi

if [[ "$DELETE" != "1" ]]; then
  cat <<EOF

Dry-run only. After you finish reviewing trunk:
  1. Confirm GitHub CI is green on $TRUNK
  2. Optionally set the repo default branch to main (Settings → General)
  3. Re-run: CONFIRM=yes DELETE=1 ./scripts/collapse-stack.sh --delete
EOF
  exit 0
fi

if [[ "${CONFIRM:-}" != "yes" ]]; then
  echo "refusing delete: set CONFIRM=yes" >&2
  exit 2
fi
if [[ "$unmerged" -ne 0 ]]; then
  echo "refusing delete: $unmerged tip(s) not contained in $TRUNK" >&2
  exit 1
fi

for branch in "${STACK_BRANCHES[@]}" "${CHERRY_PICKED_BRANCHES[@]}"; do
  if git rev-parse --verify -q "$REMOTE/$branch" >/dev/null; then
    git push "$REMOTE" --delete "$branch"
  fi
done
echo "stack remote branches deleted"
