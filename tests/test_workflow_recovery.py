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
    proposal_path = tmp_path / ".ai/workflow-pr-proposals/feature.json"
    proposal_path.parent.mkdir(parents=True)
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
    proposal = json.loads(proposal_path.read_text())
    assert proposal["status"] == "PR_OPEN"
    assert proposal["merge_approval"] == {"status": "required"}
    assert recovery.pending_workflow_merge_approvals(tmp_path) == [{
        "pr_url": "https://github.com/Dolan001/agents/pull/3",
        "repository": "Dolan001/agents",
        "base_branch": "dev",
        "proposal": ".ai/workflow-pr-proposals/feature.json",
    }]
    assert any(argv[:2] == ["git", "push"] for argv in commands)
    assert any(argv[:3] == ["gh", "pr", "create"] for argv in commands)
    assert not any(argv[:3] == ["gh", "pr", "merge"] for argv in commands)
    monkeypatch.delenv("AI_WORKFLOW_PR_ATTEMPTED")


def test_only_open_recorded_workflow_prs_request_merge_approval(tmp_path: Path) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    (directory / "closed.json").write_text(json.dumps({
        "status": "MERGED", "pr_url": "https://github.com/Dolan001/agents/pull/5",
        "merge_approval": {"status": "required"},
    }))
    (directory / "other.json").write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": "https://github.com/Dolan001/base/pull/7",
    }))
    assert recovery.pending_workflow_merge_approvals(tmp_path) == []
    (directory / "other.json").write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": "https://github.com/Dolan001/base/pull/7",
        "merge_approval": {"status": "required"}, "repository": "Dolan001/base",
        "base_branch": "dev",
    }))
    assert recovery.pending_workflow_merge_approvals(tmp_path) == [{
        "pr_url": "https://github.com/Dolan001/base/pull/7",
        "repository": "Dolan001/base", "base_branch": "dev",
        "proposal": ".ai/workflow-pr-proposals/other.json",
    }]


def test_project_status_exposes_pending_workflow_merge_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    (directory / "backend.json").write_text(json.dumps({
        "status": "PR_OPEN",
        "pr_url": "https://github.com/Dolan001/agents/pull/8",
        "repository": "Dolan001/agents",
        "base_branch": "dev",
        "merge_approval": {"status": "required"},
    }))
    monkeypatch.setattr(cli, "resolved_project", lambda _project: tmp_path)
    monkeypatch.setattr(cli, "StateStore", lambda _project: argparse.Namespace(
        load=lambda: {"project_id": "example", "status": "running", "current_phase": "backend"}
    ))
    monkeypatch.setattr(cli, "issue_summary", lambda _project: {})
    monkeypatch.setattr(cli, "selected_pack_status", lambda _project: {})
    monkeypatch.setattr(cli, "progress_snapshot", lambda _project: {})
    assert cli.command_status(argparse.Namespace(project=str(tmp_path), json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["workflow_merge_approvals"][0]["pr_url"].endswith("/pull/8")


def test_project_merge_requires_exact_head_and_records_github_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    proposal_path = directory / "backend.json"
    url = "https://github.com/Dolan001/agents/pull/8"
    proposal_path.write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": url, "commit": "abc123",
        "repository": "Dolan001/agents", "base_branch": "dev",
        "merge_approval": {"status": "required"},
    }))
    commands: list[list[str]] = []
    merged = False

    def command(_repo: Path, argv: list[str], **_kwargs: object) -> str:
        nonlocal merged
        commands.append(argv)
        if argv[:3] == ["gh", "pr", "view"]:
            return json.dumps({
                "state": "MERGED" if merged else "OPEN",
                "baseRefName": "dev", "headRefOid": "abc123",
                "mergeable": "MERGEABLE", "mergeCommit": {"oid": "merge456"},
            })
        if argv[:3] == ["gh", "pr", "merge"]:
            assert argv[-2:] == ["--match-head-commit", "abc123"]
            merged = True
            return ""
        raise AssertionError(argv)

    monkeypatch.setattr(recovery, "_command", command)
    assert recovery.merge_approved_workflow_pr(tmp_path, url)["base_branch"] == "dev"
    saved = json.loads(proposal_path.read_text())
    assert saved["status"] == "MERGED"
    assert saved["merge_commit"] == "merge456"
    assert recovery.pending_workflow_merge_approvals(tmp_path) == []
    assert len([argv for argv in commands if argv[:3] == ["gh", "pr", "merge"]]) == 1


def test_project_merge_rejects_changed_pr_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    url = "https://github.com/Dolan001/agents/pull/8"
    (directory / "backend.json").write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": url, "commit": "abc123",
        "repository": "Dolan001/agents", "base_branch": "dev",
        "merge_approval": {"status": "required"},
    }))
    commands: list[list[str]] = []

    def command(_repo: Path, argv: list[str], **_kwargs: object) -> str:
        commands.append(argv)
        return json.dumps({
            "state": "OPEN", "baseRefName": "dev", "headRefOid": "changed",
            "mergeable": "MERGEABLE",
        })

    monkeypatch.setattr(recovery, "_command", command)
    with pytest.raises(RuntimeError, match="head changed"):
        recovery.merge_approved_workflow_pr(tmp_path, url)
    assert not any(argv[:3] == ["gh", "pr", "merge"] for argv in commands)


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
