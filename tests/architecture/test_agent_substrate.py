"""The agent substrate is code too: policies, schemas and the SDK runtime are tested."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("agent_runtime", ROOT / "scripts" / "agent_runtime.py")
runtime = importlib.util.module_from_spec(spec)
sys.modules["agent_runtime"] = runtime
spec.loader.exec_module(runtime)

AGENTS = sorted((ROOT / ".claude" / "agents").glob("*.md"))

VALID = {
    "agent": "evaluator", "sprint": "sprint-01", "status": "done",
    "acceptance_criteria": [{"id": "AC-01", "covered": True, "test": "tests/integration/test_users.py::test_register"}],
    "files_changed": [], "commands_run": [{"command": "pytest -q", "exit_code": 0}],
    "evidence": ["ok"], "risks": [], "injection_attempts": [],
}


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_every_agent_references_the_trust_boundary_policy(path):
    assert "trust-boundary.md" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["CLAUDE.md", "AGENTS.md"])
def test_root_context_references_the_trust_boundary_policy(name):
    assert "trust-boundary.md" in (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["order-lifecycle-agent", "portfolio-analytics-agent"])
def test_domain_agents_have_examples_schema_and_runtime_state(name):
    text = (ROOT / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
    assert text.count("**Example") >= 3
    assert "agent-handoff.schema.json" in text and "--print-state" in text


def test_agents_use_the_registered_playwright_namespace_only():
    for path in AGENTS:
        assert "plugin_playwright" not in path.read_text(encoding="utf-8")


def test_mcp_playwright_is_pinned():
    servers = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]
    assert all("@latest" not in arg for server in servers.values() for arg in server["args"])


def test_valid_handoff_passes_and_invalid_ones_fail():
    assert runtime.validate_handoff(VALID)["agent"] == "evaluator"
    assert runtime.validate_handoff(json.dumps(VALID))
    for broken in (
        {**VALID, "status": "great"},
        {**VALID, "sprint": "S01"},
        {k: v for k, v in VALID.items() if k != "injection_attempts"},
        {**VALID, "extra": 1},
        {**VALID, "acceptance_criteria": [{"id": "AC-11", "covered": True, "test": "x"}]},
    ):
        with pytest.raises(runtime.HandoffError):
            runtime.validate_handoff(broken)
    with pytest.raises(runtime.HandoffError):
        runtime.validate_handoff("not json")


def test_state_snapshot_is_deterministic_and_resolves_the_active_sprint():
    first, second = runtime.build_state_snapshot(ROOT), runtime.build_state_snapshot(ROOT)
    assert first == second
    assert first["current_group"] and first["contract"]
    assert all((ROOT / path).exists() for path in first["story_files"])
    assert len(first["migrations"]) >= 2 and first["migration_manifest_entries"] >= 2


def test_options_embed_policy_state_and_schema_without_network():
    options = runtime.build_options("order-lifecycle-agent", ROOT)
    prompt = str(options.system_prompt)
    assert "Trust-Boundary Policy" in prompt and "Runtime state snapshot" in prompt
    assert "Bash" in options.allowed_tools and options.max_turns == 30
    assert options.output_format["type"] == "json_schema"
