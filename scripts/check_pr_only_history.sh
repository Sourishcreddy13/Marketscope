#!/usr/bin/env bash
# PR-only merge rule, verified from history: every commit on the first-parent line of the branch
# (except the root commit) must be a merge commit, i.e. a merged PR/MR. Direct commits fail.
# Usage: scripts/check_pr_only_history.sh [branch]   (default origin/main)
set -euo pipefail
BRANCH="${1:-origin/main}"
bad=0
while read -r sha parents; do
  # `parents` is the space separated parent list; a merge has two or more, the root has none.
  [[ -z "${parents:-}" ]] && continue
  if [[ "$parents" != *" "* ]]; then
    echo "DIRECT COMMIT on ${BRANCH}: $(git log -1 --format='%h %an: %s' "$sha")"
    bad=1
  fi
done < <(git rev-list --first-parent --parents "$BRANCH")
exit $bad
