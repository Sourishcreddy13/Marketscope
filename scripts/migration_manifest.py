"""Append-only guard for Alembic migrations (NFR-05).

`migrations/MANIFEST.sha256` records the SHA-256 of every merged migration file. A migration that is
edited, renamed or deleted no longer matches its manifest line, so the check fails. New migrations must
be *appended* with `python -m scripts.migration_manifest append`, which refuses to touch existing lines.
CI additionally compares the manifest against the target branch so history cannot be rewritten by
editing the manifest itself (`check --base origin/main`).

Usage:
    python -m scripts.migration_manifest check [--base REF]
    python -m scripts.migration_manifest append
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
MANIFEST = MIGRATIONS / "MANIFEST.sha256"


def file_digest(path: Path) -> str:
    """SHA-256 of the file with CRLF normalized, so Windows checkouts hash identically."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def current_files(migrations_dir: Path = MIGRATIONS) -> dict[str, str]:
    versions = migrations_dir / "versions"
    return {f"versions/{p.name}": file_digest(p) for p in sorted(versions.glob("*.py")) if p.name != "__init__.py"}


def parse_manifest(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        entries[name.strip()] = digest.strip()
    return entries


def load_manifest(path: Path = MANIFEST) -> dict[str, str]:
    return parse_manifest(path.read_text(encoding="utf-8")) if path.exists() else {}


def render(entries: dict[str, str]) -> str:
    header = "# Append-only migration manifest (NFR-05). Never edit or remove a line; add new ones with `append`.\n"
    return header + "".join(f"{digest}  {name}\n" for name, digest in sorted(entries.items()))


def verify(manifest: dict[str, str], files: dict[str, str]) -> list[str]:
    """Return human-readable violations (empty list = history intact)."""
    problems: list[str] = []
    for name, digest in manifest.items():
        if name not in files:
            problems.append(f"{name}: merged migration was deleted or renamed")
        elif files[name] != digest:
            problems.append(f"{name}: merged migration was modified in place (add a new migration instead)")
    for name in files:
        if name not in manifest:
            problems.append(f"{name}: new migration is not registered; run `python -m scripts.migration_manifest append`")
    return problems


def verify_against_base(base: dict[str, str], current: dict[str, str]) -> list[str]:
    """The manifest may only grow: every base line must survive unchanged."""
    problems: list[str] = []
    for name, digest in base.items():
        if name not in current:
            problems.append(f"manifest line for {name} was removed")
        elif current[name] != digest:
            problems.append(f"manifest hash for {name} was rewritten")
    return problems


def append_new(manifest: dict[str, str], files: dict[str, str]) -> dict[str, str]:
    """Register unregistered migrations; raises if an existing entry would change."""
    changed = [n for n, d in manifest.items() if n in files and files[n] != d]
    if changed:
        raise SystemExit(f"Refusing to append: merged migrations were modified: {', '.join(changed)}")
    return {**manifest, **{n: d for n, d in files.items() if n not in manifest}}


def _base_manifest(ref: str) -> dict[str, str]:
    result = subprocess.run(
        ["git", "show", f"{ref}:migrations/MANIFEST.sha256"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return parse_manifest(result.stdout) if result.returncode == 0 else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--base", help="git ref of the target branch to compare the manifest against")
    sub.add_parser("append")
    args = parser.parse_args(argv)

    files = current_files()
    manifest = load_manifest()
    if args.command == "append":
        MANIFEST.write_text(render(append_new(manifest, files)), encoding="utf-8")
        print(f"Manifest now lists {len(load_manifest())} migrations.")
        return 0

    problems = verify(manifest, files)
    if args.base:
        problems += verify_against_base(_base_manifest(args.base), manifest)
    for problem in problems:
        print(f"MIGRATION_IMMUTABILITY_ERROR: {problem}", file=sys.stderr)
    if not problems:
        print(f"Migration history intact ({len(manifest)} merged migrations).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
