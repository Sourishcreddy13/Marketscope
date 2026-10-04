#!/usr/bin/env bash
# Create .env from .env.example with a freshly generated JWT secret if .env does not exist.
# Never overwrites an existing .env. The secret is generated locally and is never committed (.env is git-ignored).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  # An existing .env with an empty JWT_SECRET (a copied template) is completed, never overwritten.
  if grep -Eq '^JWT_SECRET=[[:space:]]*$' .env; then
    secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    python3 - "$secret" <<'PY'
import pathlib, re, sys
path = pathlib.Path(".env")
path.write_text(re.sub(r"(?m)^JWT_SECRET=\s*$", f"JWT_SECRET={sys.argv[1]}", path.read_text()))
PY
    echo "Filled the empty JWT_SECRET in .env."
  fi
  exit 0
fi
secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
sed "s|^JWT_SECRET=.*|JWT_SECRET=${secret}|" .env.example > .env
chmod 600 .env
echo "Created .env with a generated JWT_SECRET (git-ignored)."
