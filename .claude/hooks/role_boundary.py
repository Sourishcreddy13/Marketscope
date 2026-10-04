#!/usr/bin/env python3
"""Path-aware role-boundary analysis for FastAPI controllers (NFR-04).

Rules, derived from the router prefix and the route path:
  * every route whose full path starts with /admin MUST depend on `require_admin`;
  * every other route MUST depend on `get_current_user` (the standard authenticated dependency)
    and MUST NOT depend on `require_admin` (an admin-only operation belongs under /admin);
  * the only public routes are the explicit allow-list below.

Used by .claude/hooks/role-boundary-check.sh (pre-commit) and tests/architecture.
Pure standard library so it runs in any hook environment.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_ROUTES = {("POST", "/auth/register"), ("POST", "/auth/login")}
ADMIN_DEP = "require_admin"
CUSTOMER_DEP = "get_current_user"


def _depends_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and getattr(child.func, "id", None) == "Depends" and child.args:
            arg = child.args[0]
            if isinstance(arg, ast.Name):
                names.add(arg.id)
    return names


def _str_arg(call: ast.Call, index: int, keyword: str) -> str | None:
    if len(call.args) > index and isinstance(call.args[index], ast.Constant):
        return str(call.args[index].value)
    for kw in call.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def analyze_source(source: str, filename: str = "<api>") -> list[str]:
    tree = ast.parse(source, filename=filename)
    router_prefix, router_deps = "", set[str]()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "APIRouter":
            call = node.value
            router_prefix = _str_arg(call, 99, "prefix") or ""
            router_deps = set()
            for kw in call.keywords:
                if kw.arg == "dependencies":
                    router_deps = _depends_names(kw.value)

    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
                continue
            method = decorator.func.attr
            if method not in HTTP_METHODS or getattr(decorator.func.value, "id", None) != "router":
                continue
            route = (_str_arg(decorator, 0, "path") or "")
            full_path = f"{router_prefix}{route}"
            deps = set(router_deps) | _depends_names(node.args) | _depends_names(decorator)
            where = f"{filename}:{node.lineno} {method.upper()} {full_path or '/'} ({node.name})"
            if (method.upper(), full_path) in PUBLIC_ROUTES:
                continue
            if full_path.startswith("/admin"):
                if ADMIN_DEP not in deps:
                    problems.append(f"{where}: /admin route must depend on {ADMIN_DEP}")
            else:
                if ADMIN_DEP in deps:
                    problems.append(f"{where}: admin-only dependency on a non-/admin route; move it under /admin")
                if CUSTOMER_DEP not in deps:
                    problems.append(f"{where}: customer route must depend on {CUSTOMER_DEP}")
    return problems


def analyze_directory(api_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(api_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        problems.extend(analyze_source(path.read_text(encoding="utf-8"), str(path)))
    return problems


def main(argv: list[str]) -> int:
    api_dir = Path(argv[1]) if len(argv) > 1 else Path("app/api")
    problems = analyze_directory(api_dir)
    for problem in problems:
        print(f"ROLE_BOUNDARY_ERROR: {problem}")
    if not problems:
        print("Role-boundary check passed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
