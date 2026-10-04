#!/usr/bin/env bash
# PreToolUse(Bash) on `git commit`, or standalone with --all: NFR-01 fixed-point guardrail.
# Rejects binary floating point in every financial code path. Append `# precision-ok` (or `// precision-ok`)
# to a line that is provably non-financial (e.g. a timestamp), which keeps exceptions visible in review.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 0

if [[ "${1:-}" != "--all" ]]; then
  INPUT="$(cat)"
  COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)"
  [[ "$COMMAND" == *"git commit"* ]] || exit 0
fi

status=0
report() { echo "MATH_PRECISION_ERROR: $1" >&2; status=1; }

# Financial Python: domain, models (ORM column types), services, repositories, API arithmetic, and migrations.
PY_TARGETS=()
for dir in app/domain app/models app/services app/repositories app/api migrations; do
  [[ -d "$dir" ]] && PY_TARGETS+=("$dir")
done
if ((${#PY_TARGETS[@]})); then
  matches="$(grep -rnE --include='*.py' --include='*.sql' \
    -e '\bfloat\b' -e '\bFloat\b' -e '\bDOUBLE\b' -e '\bFLOAT\b' -e '\bREAL\b' -e 'numpy' \
    -e 'Decimal\(\s*-?[0-9]+\.[0-9]' -e 'sa\.Float|sa\.REAL|sa\.Double' \
    "${PY_TARGETS[@]}" 2>/dev/null | grep -v 'precision-ok' || true)"
  if [[ -n "$matches" ]]; then
    report "floating-point usage in financial Python/SQL paths:"
    printf '%s\n' "$matches" >&2
  fi
fi

# Financial presentation code: never convert authoritative decimal strings to JS numbers.
if [[ -d frontend/src ]]; then
  matches="$(grep -rnE --include='*.ts' --include='*.tsx' --exclude='*.test.ts' --exclude='*.test.tsx' \
    -e '\bNumber\(' -e 'parseFloat' -e '\.toFixed\(' -e '\bMath\.(round|floor|ceil)\(' \
    frontend/src 2>/dev/null | grep -v 'precision-ok' || true)"
  if [[ -n "$matches" ]]; then
    report "JavaScript number conversion in frontend financial code (use decimal-string helpers in src/lib/format.ts):"
    printf '%s\n' "$matches" >&2
  fi
fi

if [[ $status -ne 0 ]]; then
  echo "Fix: use Decimal / FixedDecimal (Python) and decimal-string helpers (TypeScript)." >&2
  exit 2
fi
echo "Math-precision check passed."
