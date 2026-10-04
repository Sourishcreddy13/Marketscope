#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_payload(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError("Root JSON value must be an object.")
    return value


def validate(payload: dict) -> list[str]:
    errors: list[str] = []

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string.")

    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        errors.append("symbols must be an array.")
        return errors

    if len(symbols) < 1:
        errors.append("watchlist must contain at least one symbol.")

    seen: set[str] = set()
    for index, symbol in enumerate(symbols):
        if not isinstance(symbol, str):
            errors.append(f"symbols[{index}] must be a string.")
            continue
        normalized = symbol.strip().upper()
        if not normalized:
            errors.append(f"symbols[{index}] must not be empty.")
            continue
        if normalized in seen:
            errors.append(f"duplicate symbol: {normalized}")
        seen.add(normalized)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a MarketScope watchlist payload.")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    try:
        payload = load_payload(args.input)
        errors = validate(payload)
    except ValueError as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print(json.dumps({
        "valid": True,
        "name": payload["name"].strip(),
        "normalized_symbols": sorted({s.strip().upper() for s in payload["symbols"]}),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
