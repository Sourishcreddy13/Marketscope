"""Architecture rules as automated tests (NFR-08, NFR-02, NFR-04, NFR-05).

Layering is enforced by import-linter contracts in pyproject.toml; the tests here run that tool and add
the project-specific rules it cannot express. Structural checks use the AST, never string matching.
"""
import ast
import importlib.util
import inspect
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.repositories.repositories import TradeRepository

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
FINANCIAL_PACKAGES = ["domain", "models", "services", "repositories", "api"]


def run_lint_imports(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("lint-imports") or str(Path(sys.executable).parent / "lint-imports")
    return subprocess.run([executable, *args], cwd=cwd, capture_output=True, text=True, check=False)


def python_files(package: str):
    return sorted((APP / package).rglob("*.py"))


# ----------------------------------------------------------------------------- layering (import-linter)


@pytest.mark.nfr08
def test_import_linter_contracts_are_kept():
    result = run_lint_imports(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.nfr08
def test_import_linter_actually_detects_a_layer_violation(tmp_path):
    """Guard against a vacuous contract: a deliberately inverted import must fail the tool."""
    package = tmp_path / "toy"
    for name in ("api", "domain"):
        (package / name).mkdir(parents=True)
        (package / name / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "api" / "routes.py").write_text("VALUE = 1\n")
    (package / "domain" / "rules.py").write_text("from toy.api import routes  # domain reaching up: forbidden\n")
    (tmp_path / "setup.cfg").write_text(
        textwrap.dedent(
            """
            [importlinter]
            root_package = toy

            [importlinter:contract:layers]
            name = layers
            type = layers
            layers =
                toy.api
                toy.domain
            """
        )
    )
    result = run_lint_imports(tmp_path, "--config", "setup.cfg")
    assert result.returncode != 0
    assert "BROKEN" in result.stdout


@pytest.mark.nfr08
def test_domain_package_has_no_framework_imports():
    banned = {"fastapi", "sqlalchemy", "pydantic", "starlette"}
    for path in python_files("domain"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert module.split(".")[0] not in banned, f"{path.name} imports {module}"
                assert not module.startswith("app.") or module.startswith("app.domain"), f"{path.name} imports {module}"


# ----------------------------------------------------------------------------- NFR-01 fixed-point


def _float_usages(path: Path) -> list[str]:
    found = []
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        line = getattr(node, "lineno", 0)
        if line and "precision-ok" in lines[line - 1]:
            continue
        if isinstance(node, ast.Name) and node.id in {"float", "Float"}:
            found.append(f"{path.relative_to(ROOT)}:{line} uses {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"{path.relative_to(ROOT)}:{line} float literal {node.value}")
        elif isinstance(node, ast.Attribute) and node.attr in {"Float", "Double", "REAL", "FLOAT"}:
            found.append(f"{path.relative_to(ROOT)}:{line} uses {node.attr}")
    return found


@pytest.mark.nfr01
def test_no_binary_floating_point_in_financial_code():
    offenders = [item for package in FINANCIAL_PACKAGES for path in python_files(package) for item in _float_usages(path)]
    offenders += [item for path in sorted((ROOT / "migrations").rglob("*.py")) for item in _float_usages(path)]
    assert offenders == []


@pytest.mark.nfr01
def test_float_detector_catches_violations(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import sqlalchemy as sa\nx = float('1.5')\ny = 0.1\nz = sa.Float()\n")
    ok = tmp_path / "ok.py"
    ok.write_text("import math\nf = float  # precision-ok\n")
    # _float_usages reports paths relative to ROOT, so use absolute fallback for tmp files.
    bad_usages = [u for u in _float_usages_abs(bad)]
    assert len(bad_usages) >= 3
    assert _float_usages_abs(ok) == []


def _float_usages_abs(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    out = []
    for node in ast.walk(ast.parse(source)):
        line = getattr(node, "lineno", 0)
        if line and "precision-ok" in lines[line - 1]:
            continue
        if (isinstance(node, ast.Name) and node.id in {"float", "Float"}) or (
            isinstance(node, ast.Constant) and isinstance(node.value, float)
        ) or (isinstance(node, ast.Attribute) and node.attr in {"Float", "Double"}):
            out.append(f"{line}")
    return out


# ----------------------------------------------------------------------------- NFR-02 append-only


@pytest.mark.nfr02
def test_trade_repository_exposes_no_mutating_operations():
    public = {name for name, member in inspect.getmembers(TradeRepository, inspect.isfunction) if not name.startswith("_")}
    assert public == {"add", "get_for_order", "list_for_customer", "list_recent"}


@pytest.mark.nfr02
def test_application_code_never_deletes_orders_trades_or_events():
    forbidden_targets = {"Order", "Trade", "OrderEvent", "AuditEvent", "MarketTick"}
    for package in ("services", "repositories", "api"):
        for path in python_files(package):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "delete":
                    for arg in node.args:
                        name = getattr(arg, "id", None) or getattr(getattr(arg, "func", None), "id", None)
                        assert name not in forbidden_targets, f"{path.name}:{node.lineno} deletes {name}"


# ----------------------------------------------------------------------------- NFR-04 role boundaries


def _dependency_callables(dependant):
    for sub in dependant.dependencies:
        yield sub.call
        yield from _dependency_callables(sub)


def _flatten_routes(routes, prefix=""):
    """Yield (full_path, APIRoute), resolving FastAPI's lazily included routers (original_router + include prefix)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif hasattr(route, "original_router"):
            extra = getattr(route.include_context, "prefix", "") or ""
            yield from _flatten_routes(route.original_router.routes, prefix + extra)


PUBLIC_PATHS = {"/health", "/api/v1/auth/login", "/api/v1/auth/register", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


@pytest.mark.nfr04
def test_every_admin_route_requires_admin_and_every_other_route_requires_authentication():
    from app.core.dependencies import get_current_user, require_admin

    checked = 0
    for path, route in _flatten_routes(app.routes):
        if path in PUBLIC_PATHS:
            continue
        calls = set(_dependency_callables(route.dependant))
        if path.startswith("/api/v1/admin"):
            assert require_admin in calls, f"{route.methods} {path} is reachable without require_admin"
        else:
            assert get_current_user in calls, f"{route.methods} {path} is reachable without authentication"
            assert require_admin not in calls, f"{path} is admin-only but lives outside /admin"
        checked += 1
    assert checked >= 20


def _load_role_boundary():
    spec = importlib.util.spec_from_file_location("role_boundary", ROOT / ".claude" / "hooks" / "role_boundary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.nfr04
def test_role_boundary_hook_accepts_the_real_controllers():
    assert _load_role_boundary().analyze_directory(APP / "api") == []


@pytest.mark.nfr04
def test_role_boundary_hook_flags_an_admin_route_with_ordinary_authentication():
    module = _load_role_boundary()
    source = textwrap.dedent(
        """
        from fastapi import APIRouter, Depends
        router = APIRouter(prefix="/admin", tags=["admin"])

        @router.get("/secrets")
        def secrets(user=Depends(get_current_user)):
            return {}
        """
    )
    problems = module.analyze_source(source, "admin_leak.py")
    assert len(problems) == 1 and "require_admin" in problems[0]


@pytest.mark.nfr04
def test_role_boundary_hook_flags_unauthenticated_and_misplaced_routes():
    module = _load_role_boundary()
    source = textwrap.dedent(
        """
        from fastapi import APIRouter, Depends
        router = APIRouter(prefix="/orders")

        @router.get("")
        def open_route():
            return []

        @router.post("/purge")
        def admin_only_outside_admin(user=Depends(require_admin)):
            return {}
        """
    )
    problems = module.analyze_source(source, "orders.py")
    assert any("get_current_user" in p for p in problems)
    assert any("move it under /admin" in p for p in problems)


@pytest.mark.nfr04
def test_role_boundary_hook_honours_router_level_dependencies():
    module = _load_role_boundary()
    source = textwrap.dedent(
        """
        from fastapi import APIRouter, Depends
        router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

        @router.get("/ok")
        def ok():
            return {}
        """
    )
    assert module.analyze_source(source, "admin_ok.py") == []
