import argparse
import json
import subprocess
from pathlib import Path

import pytest

import ai_workflow.cli as cli
import ai_workflow.execution as execution
import ai_workflow.workflow_recovery as recovery


def test_repair_target_rejects_paths_outside_workflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(recovery, "workflow_root", lambda: tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/engine.py").write_text("pass\n")
    repo, paths = recovery._repair_target({
        "findings": [{"paths": ["src/engine.py"]}],
    })
    assert repo == tmp_path and paths == ["src/engine.py"]
    with pytest.raises(RuntimeError, match="unsafe"):
        recovery._repair_target({"findings": [{"paths": ["../private.txt"]}]})
    outside = tmp_path.parent / "outside-workflow.py"
    outside.write_text("pass\n")
    (tmp_path / "src/link.py").symlink_to(outside)
    with pytest.raises(RuntimeError, match="unsafe"):
        recovery._repair_target({"findings": [{"paths": ["src/link.py"]}]})


def test_workflow_repair_tests_publishes_pr_and_keeps_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AI_WORKFLOW_PR_ATTEMPTED", raising=False)
    monkeypatch.setattr(recovery, "workflow_root", lambda: tmp_path)
    source = tmp_path / "src/engine.py"
    source.parent.mkdir()
    source.write_text("before\n")
    proposal_path = tmp_path / ".ai/proposal.json"
    proposal_path.parent.mkdir()
    proposal_path.write_text(json.dumps({
        "status": "PR_REQUIRED",
        "findings": [{"paths": ["src/engine.py"], "details": "Retry loop drops state."}],
    }))
    commands: list[list[str]] = []

    def command(_repo: Path, argv: list[str], **_kwargs) -> str:
        commands.append(argv)
        if argv[:3] == ["git", "remote", "get-url"]:
            return "https://github.com/Dolan001/agents.git"
        if argv[:3] == ["git", "branch", "--list"]:
            return "dev"
        if argv[:3] == ["git", "diff", "--name-only"]:
            return "src/engine.py\ntests/test_engine.py"
        if argv[:3] == ["git", "rev-parse", "HEAD"]:
            return "abc123"
        if argv[:3] == ["gh", "pr", "create"]:
            return "https://github.com/Dolan001/agents/pull/3"
        return ""

    def adapter(_repo: Path, _adapter: str, prompt: str, **kwargs) -> dict:
        assert kwargs["refresh_projection"] is False
        source.write_text("after\n")
        test = tmp_path / "tests/test_engine.py"
        test.parent.mkdir()
        test.write_text("def test_fixed(): assert True\n")
        output = next(part for part in prompt.split() if part.startswith(".ai/evidence/"))
        evidence = tmp_path / output
        evidence.parent.mkdir(parents=True)
        evidence.write_text(json.dumps({
            "feature_id": "workflow-recovery", "requirement_ids": ["WF-001"],
            "changed_files": ["src/engine.py", "tests/test_engine.py"],
            "checks": [{"name": "focused", "status": "passed"}],
            "reviews": [], "verified": False,
        }))
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(recovery, "_command", command)
    monkeypatch.setattr(execution, "_run_adapter", adapter)
    monkeypatch.setattr(execution, "_acquire_path_lease", lambda *_: None)
    monkeypatch.setattr(execution, "_release_path_lease", lambda *_: None)
    monkeypatch.setattr(
        recovery.subprocess, "run",
        lambda *_, **__: subprocess.CompletedProcess([], 0, "1 passed", ""),
    )
    result = recovery.repair_workflow_and_open_pr(tmp_path, "codex-reviewed", proposal_path)
    assert result["url"] == "https://github.com/Dolan001/agents/pull/3"
    assert json.loads(proposal_path.read_text())["status"] == "PR_OPEN"
    assert any(argv[:2] == ["git", "push"] for argv in commands)
    assert any(argv[:3] == ["gh", "pr", "create"] for argv in commands)
    monkeypatch.delenv("AI_WORKFLOW_PR_ATTEMPTED")


def test_cli_restarts_original_command_once_after_workflow_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = tmp_path / ".agents/bin/ai"
    runner.parent.mkdir(parents=True)
    runner.write_text("#!/bin/sh\n")
    proposal = tmp_path / ".ai/proposal.json"
    proposal.parent.mkdir()
    proposal.write_text("{}")

    def fail(_args):
        raise execution.WorkflowRepairNeeded(proposal, "workflow bug")

    args = argparse.Namespace(
        adapter="codex-reviewed", project=str(tmp_path), command="start-backend",
        handler=fail,
    )
    monkeypatch.setattr(
        cli, "parser", lambda: argparse.Namespace(parse_args=lambda _arguments: args)
    )
    monkeypatch.setattr(cli, "resolve_adapter", lambda *_: "codex-reviewed")
    monkeypatch.setattr(
        cli, "repair_workflow_and_open_pr",
        lambda *_: {"url": "https://github.com/Dolan001/agents/pull/3"},
    )
    seen = []

    def run(argv, **kwargs):
        seen.append((argv, kwargs["env"]["AI_WORKFLOW_RECOVERY_DEPTH"]))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.main(["start-backend", "--project", str(tmp_path)]) == 0
    assert seen == [
        ([str(runner), "start-backend", "--project", str(tmp_path)], "1")
    ]
