#!/usr/bin/env bash
# PreToolUse(Bash) on `git commit`, or standalone with --all: path-aware role-boundary analysis (NFR-04).
#   * every /admin/** route must depend on require_admin
#   * every customer route must depend on get_current_user and must not depend on require_admin
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 0

if [[ "${1:-}" != "--all" ]]; then
  INPUT="$(cat)"
  COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)"
  [[ "$COMMAND" == *"git commit"* ]] || exit 0
fi

PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "ROLE_BOUNDARY_ERROR: python is required to run the role-boundary analysis" >&2
  exit 2
fi
if ! output="$("$PYTHON" .claude/hooks/role_boundary.py app/api 2>&1)"; then
  printf '%s\n' "$output" >&2
  exit 2
fi
echo "$output"
