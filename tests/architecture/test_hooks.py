"""Behavioural tests for the Claude Code hooks: exit code 2 must block, 0 must allow.

Hooks are the technical enforcement of the substrate rules, so they are exercised with realistic
tool-call JSON instead of being trusted by inspection.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required to run hook scripts")


def run_hook(name: str, payload: dict, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    import os

    return subprocess.run(
        [NODE, str(HOOKS / name)], input=json.dumps(payload), capture_output=True, text=True,
        cwd=ROOT, env={**os.environ, **(env or {})}, timeout=60,
    )


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push -f origin feature/x",
        "git push --force-with-lease origin feature/x",
        "git commit --no-verify -m x",
        "git push origin HEAD:main",
        "git push origin :main",
    ],
)
def test_branch_protection_blocks_unsafe_git(command):
    result = run_hook("branch-protection.js", bash(command))
    assert result.returncode == 2, result.stderr
    assert "PR_ONLY_MERGE_RULE" in result.stderr


@pytest.mark.parametrize("command", ["git status", "git push origin feature/orders", "ls -la", "git diff HEAD"])
def test_branch_protection_allows_safe_commands(command):
    assert run_hook("branch-protection.js", bash(command)).returncode == 0


def test_branch_protection_blocks_commit_after_switching_to_main():
    assert run_hook("branch-protection.js", bash("git checkout main && git commit -m x")).returncode == 2


def test_protected_branches_are_extensible():
    result = run_hook("branch-protection.js", bash("git push origin release"), env={"PROTECTED_BRANCHES": "release"})
    assert result.returncode == 2


def test_hooks_ignore_malformed_input_without_crashing():
    result = subprocess.run([NODE, str(HOOKS / "branch-protection.js")], input="not json", capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0


def test_gate_runner_fails_closed_when_tool_is_missing():
    script = (
        "const {runGate}=require(process.argv[1]);"
        "runGate('TEST','definitely-not-an-installed-binary',[],{cwd:process.cwd()});"
    )
    result = subprocess.run([NODE, "-e", script, str(HOOKS / "lib" / "gate.js")], capture_output=True, text=True)
    assert result.returncode == 2
    assert "GATE_UNAVAILABLE" in result.stderr


def test_gate_runner_blocks_on_nonzero_exit_and_passes_on_zero():
    base = "const {runGate}=require(process.argv[1]);"
    gate = str(HOOKS / "lib" / "gate.js")
    bad = subprocess.run([NODE, "-e", base + "runGate('T','sh',['-c','echo boom >&2; exit 3']);", gate], capture_output=True, text=True)
    good = subprocess.run([NODE, "-e", base + "runGate('T','true',[]);", gate], capture_output=True, text=True)
    assert bad.returncode == 2 and "boom" in bad.stderr
    assert good.returncode == 0


def test_math_precision_hook_flags_float_in_domain_code(tmp_path):
    script = HOOKS / "math-precision-check.sh"
    assert script.exists()
    result = subprocess.run(["bash", str(script), "--all"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sprint_contracts_resolve_to_real_story_files_and_progress_group():
    contracts = sorted((ROOT / "sprint-contracts").glob("sprint-*.json"))
    assert contracts
    for contract in contracts:
        data = json.loads(contract.read_text())
        assert data["stories"], contract.name
        for story in data["stories"]:
            assert (ROOT / "specs" / "stories" / f"{story}.md").exists(), f"{contract.name}: missing story {story}"
    import re

    group = re.search(r"^current_group:\s*(\S+)", (ROOT / "claude-progress.txt").read_text(), re.M).group(1)
    assert (ROOT / "sprint-contracts" / f"{group}.json").exists()


def test_sprint_gate_blocks_commit_without_passing_evaluator_report(tmp_path):
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(HOOKS / "sprint-contract-gate.js", tmp_path / ".claude" / "hooks" / "sprint-contract-gate.js")
    (tmp_path / "claude-progress.txt").write_text("current_group: SPRINT-01\n")
    payload = json.dumps(bash("git commit -m x"))

    def run():
        return subprocess.run(
            [NODE, str(tmp_path / ".claude/hooks/sprint-contract-gate.js")], input=payload, capture_output=True, text=True, cwd=tmp_path
        )

    assert run().returncode == 2  # contract missing -> fail closed
    (tmp_path / "sprint-contracts").mkdir()
    (tmp_path / "sprint-contracts" / "sprint-01.json").write_text("{}")
    assert run().returncode == 2  # contract present, no evaluator report
    (tmp_path / "specs" / "reviews").mkdir(parents=True)
    (tmp_path / "specs" / "reviews" / "evaluator-report.md").write_text("VERDICT: PASS\n")
    assert run().returncode == 0


# ---------------------------------------------------------------- review-fix hooks


def test_task_completed_fails_closed_when_source_layout_is_missing(tmp_path):
    (tmp_path / ".claude" / "hooks" / "lib").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("")
    for name in ("task-completed.js", "lib/gate.js"):
        shutil.copy(HOOKS / name, tmp_path / ".claude" / "hooks" / name)
    result = subprocess.run([NODE, str(tmp_path / ".claude/hooks/task-completed.js")], input="{}", capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 2 and "TASK_COMPLETION_BLOCKED" in result.stderr


def test_task_completed_runs_the_real_architecture_gate():
    result = run_hook("task-completed.js", {})
    assert result.returncode == 0 and "app/" in result.stdout


def _transcript(tmp_path, *subagents):
    import time

    lines = []
    for index, name in enumerate(subagents):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() + 5 + index))
        lines.append(json.dumps({"timestamp": stamp, "message": {"content": [{"type": "tool_use", "name": "Agent", "input": {"subagent_type": name}}]}}))
    path = tmp_path / f"transcript-{abs(hash(subagents))}.jsonl"
    path.write_text("\n".join(lines))
    return path


def _require_review(tmp_path, *subagents):
    project = tmp_path / f"proj-{abs(hash(subagents))}"
    (project / ".claude" / "hooks").mkdir(parents=True)
    (project / ".claude" / "state").mkdir()
    shutil.copy(HOOKS / "require-review.js", project / ".claude" / "hooks" / "require-review.js")
    import time

    (project / ".claude" / "state" / "pending-reviews.jsonl").write_text(json.dumps({"file": "app/x.py", "ts": int(time.time() * 1000)}) + "\n")
    payload = json.dumps({"transcript_path": str(_transcript(tmp_path, *subagents))})
    return subprocess.run([NODE, str(project / ".claude/hooks/require-review.js")], input=payload, capture_output=True, text=True, cwd=project)


def test_stop_hook_needs_both_review_classes(tmp_path):
    assert "block" in _require_review(tmp_path, "security-reviewer").stdout
    assert "block" in _require_review(tmp_path, "clean-code-reviewer").stdout
    assert _require_review(tmp_path, "clean-code-reviewer", "security-reviewer").stdout.strip() == ""


def test_secret_scanner_inspects_markdown_and_incoming_content(tmp_path):
    fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
    target = tmp_path / "notes.md"
    result = run_hook("detect-secrets.js", {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": f"key {fake_key}"}})
    assert result.returncode == 2 and "AWS Access Key" in result.stdout
    clean = run_hook("detect-secrets.js", {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "no secrets here"}})
    assert clean.returncode == 0
