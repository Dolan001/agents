"""Focused safety checks for explicit workflow PR merges and repository pulls."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import ai_workflow.git_maintenance as maintenance
from ai_workflow.cli import parser

GIT = shutil.which("git")
assert GIT is not None


def test_cli_accepts_explicit_and_pending_merge_and_selected_pull() -> None:
    assert parser().parse_args(["git-merge", "base", "pr-2", "agents", "pr-6"]).targets == [
        "base", "pr-2", "agents", "pr-6",
    ]
    assert parser().parse_args(["git-merge"]).targets == []
    assert parser().parse_args(["git-pull", "--repo", "base", "drf"]).repos == [
        "base", "drf",
    ]


def test_merge_preflights_every_pr_and_orders_base_before_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = {
        "agents": {"url": "https://github.com/Dolan001/agents.git", "branch": "dev"},
        "base": {"url": "https://github.com/Dolan001/base.git", "branch": "dev"},
    }
    monkeypatch.setattr(maintenance, "_repo_root", lambda _: (tmp_path, False))
    monkeypatch.setattr(maintenance, "_catalog", lambda _: catalog)
    calls: list[str] = []
    merged: set[str] = set()

    def view(_cwd: Path, repository: str, _number: int) -> dict:
        calls.append(f"view:{repository}")
        return {
            "state": "MERGED" if repository in merged else "OPEN",
            "baseRefName": "dev", "headRefOid": "a" * 40,
            "mergeable": "MERGEABLE", "statusCheckRollup": [],
            "reviewDecision": "", "mergeCommit": {"oid": "b" * 40},
        }

    def run(_cwd: Path, *args: str, **_kwargs) -> tuple[int, str]:
        assert args[:3] == ("gh", "pr", "merge")
        repository = args[args.index("--repo") + 1]
        calls.append(f"merge:{repository}")
        merged.add(repository)
        return 0, ""

    monkeypatch.setattr(maintenance, "_pr_view", view)
    monkeypatch.setattr(maintenance, "_run", run)
    result = maintenance.merge_workflow_prs(
        tmp_path, ["agents", "pr-6", "base", "pr-2"],
    )
    assert result["status"] == "merged"
    assert calls[:2] == ["view:Dolan001/base", "view:Dolan001/agents"]
    assert [item["repository"] for item in result["merged"]] == ["base", "agents"]


def test_merge_rejects_failing_check_before_any_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance, "_repo_root", lambda _: (tmp_path, False))
    monkeypatch.setattr(maintenance, "_catalog", lambda _: {
        "base": {"url": "https://github.com/Dolan001/base.git", "branch": "dev"},
    })
    monkeypatch.setattr(maintenance, "_pr_view", lambda *_: {
        "state": "OPEN", "baseRefName": "dev", "headRefOid": "a" * 40,
        "mergeable": "MERGEABLE", "reviewDecision": "",
        "statusCheckRollup": [{"conclusion": "FAILURE"}],
    })
    monkeypatch.setattr(
        maintenance, "_run", lambda *_args, **_kwargs: pytest.fail("merge was invoked"),
    )
    with pytest.raises(RuntimeError, match="checks are pending or failing"):
        maintenance.merge_workflow_prs(tmp_path, ["base", "pr-2"])


def test_pending_merge_targets_only_recorded_approval(tmp_path: Path) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    (directory / "base.json").write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": "https://github.com/Dolan001/base/pull/2",
        "merge_approval": {"status": "required"},
    }))
    (directory / "other.json").write_text(json.dumps({
        "status": "MERGED", "pr_url": "https://github.com/Dolan001/agents/pull/6",
        "merge_approval": {"status": "approved"},
    }))
    catalog = {
        "base": {"url": "https://github.com/Dolan001/base.git", "branch": "dev"},
        "agents": {"url": "https://github.com/Dolan001/agents.git", "branch": "dev"},
    }
    assert maintenance._pending_targets(tmp_path, catalog) == [("base", 2)]


def test_merge_without_pairs_updates_only_the_recorded_pending_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / ".ai/workflow-pr-proposals"
    directory.mkdir(parents=True)
    proposal = directory / "base.json"
    proposal.write_text(json.dumps({
        "status": "PR_OPEN", "pr_url": "https://github.com/Dolan001/base/pull/2",
        "commit": "a" * 40, "merge_approval": {"status": "required"},
    }))
    monkeypatch.setattr(maintenance, "_repo_root", lambda _: (tmp_path, False))
    monkeypatch.setattr(maintenance, "_catalog", lambda _: {
        "base": {"url": "https://github.com/Dolan001/base.git", "branch": "dev"},
    })
    merged = False

    def view(_cwd: Path, _repository: str, _number: int) -> dict:
        return {
            "state": "MERGED" if merged else "OPEN", "baseRefName": "dev",
            "headRefOid": "a" * 40, "mergeable": "MERGEABLE",
            "reviewDecision": "", "statusCheckRollup": [],
            "mergeCommit": {"oid": "b" * 40},
        }

    def run(_cwd: Path, *args: str, **_kwargs) -> tuple[int, str]:
        nonlocal merged
        assert args[:3] == ("gh", "pr", "merge")
        merged = True
        return 0, ""

    monkeypatch.setattr(maintenance, "_pr_view", view)
    monkeypatch.setattr(maintenance, "_run", run)
    assert maintenance.merge_workflow_prs(tmp_path, [])["status"] == "merged"
    record = json.loads(proposal.read_text())
    assert record["status"] == "MERGED"
    assert record["merge_approval"] == {"status": "approved"}
    assert record["merge_commit"] == "b" * 40


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 - test-owned paths and Git arguments
        [GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True,
    ).stdout.strip()


def _clone_with_update(tmp_path: Path, name: str) -> tuple[Path, str, str]:
    remote = tmp_path / f"{name}.git"
    seed = tmp_path / f"{name}-seed"
    clone = tmp_path / "workspace" / name
    clone.parent.mkdir(exist_ok=True)
    subprocess.run(  # noqa: S603 - test-owned Git invocation
        [GIT, "init", "--bare", str(remote)], check=True, capture_output=True,
    )
    seed.mkdir()
    _git(seed, "init", "-b", "dev")
    _git(seed, "config", "user.name", "Workflow Test")
    _git(seed, "config", "user.email", "test@example.test")
    (seed / "README.md").write_text("first\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "first")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "dev")
    subprocess.run(  # noqa: S603 - test-owned Git invocation
        [GIT, "clone", "-b", "dev", str(remote), str(clone)],
        check=True, capture_output=True,
    )
    before = _git(clone, "rev-parse", "HEAD")
    (seed / "README.md").write_text("second\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "second")
    after = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "origin", "dev")
    return clone, before, after


def test_selected_pull_fast_forwards_and_dirty_repo_blocks_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, old_base, new_base = _clone_with_update(tmp_path, "base")
    drf, old_drf, new_drf = _clone_with_update(tmp_path, "drf")
    root = tmp_path / "workspace/agents"
    root.mkdir()
    monkeypatch.setattr(maintenance, "_repo_root", lambda _: (root, False))
    monkeypatch.setattr(maintenance, "_catalog", lambda _: {
        "agents": {"url": "https://github.com/Dolan001/agents.git", "branch": "dev"},
        "base": {"url": "https://github.com/Dolan001/base.git", "branch": "dev"},
        "drf": {"url": "https://github.com/Dolan001/drf.git", "branch": "dev"},
    })
    monkeypatch.setattr(maintenance, "_assert_origin", lambda *_: None)
    (drf / "local.txt").write_text("uncommitted\n")
    with pytest.raises(RuntimeError, match="local changes"):
        maintenance.pull_workflow_repos(tmp_path / "workspace", ["base", "drf"])
    assert _git(base, "rev-parse", "HEAD") == old_base
    assert _git(drf, "rev-parse", "HEAD") == old_drf
    (drf / "local.txt").unlink()
    result = maintenance.pull_workflow_repos(tmp_path / "workspace", ["base", "drf"])
    assert result["status"] == "updated"
    assert _git(base, "rev-parse", "HEAD") == new_base
    assert _git(drf, "rev-parse", "HEAD") == new_drf


def test_project_pull_advances_agents_and_uses_its_reviewed_pack_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base, first_base, second_base = _clone_with_update(tmp_path, "base")
    # The helper has already published two base commits. Start the agents pin at
    # the first one, then publish a newer agents commit that pins the second.
    base_remote = tmp_path / "base.git"
    agents_remote = tmp_path / "agents.git"
    agents_seed = tmp_path / "agents-seed"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(  # noqa: S603 - test-owned Git invocation
        [GIT, "init", "--bare", str(agents_remote)], check=True, capture_output=True,
    )
    agents_seed.mkdir()
    _git(agents_seed, "init", "-b", "dev")
    _git(agents_seed, "config", "user.name", "Workflow Test")
    _git(agents_seed, "config", "user.email", "test@example.test")
    _git(agents_seed, "-c", "protocol.file.allow=always", "submodule", "add",
         "-b", "dev", str(base_remote), "base")
    _git(agents_seed / "base", "checkout", "--detach", first_base)
    _git(agents_seed, "add", ".gitmodules", "base")
    _git(agents_seed, "commit", "-m", "pin first base")
    _git(agents_seed, "remote", "add", "origin", str(agents_remote))
    _git(agents_seed, "push", "-u", "origin", "dev")
    subprocess.run(  # noqa: S603 - test-owned Git invocation
        [GIT, "clone", "-b", "dev", str(agents_remote), str(project / ".agents")],
        check=True, capture_output=True,
    )
    _git(project / ".agents", "-c", "protocol.file.allow=always",
         "submodule", "update", "--init")
    assert _git(project / ".agents/base", "rev-parse", "HEAD") == first_base
    _git(agents_seed / "base", "checkout", "--detach", second_base)
    _git(agents_seed, "add", "base")
    _git(agents_seed, "commit", "-m", "pin second base")
    newer_agents = _git(agents_seed, "rev-parse", "HEAD")
    _git(agents_seed, "push", "origin", "dev")
    monkeypatch.setattr(maintenance, "_repo_root", lambda _: (project / ".agents", True))
    monkeypatch.setattr(maintenance, "_catalog", lambda _: {
        "agents": {"url": str(agents_remote), "branch": "dev"},
        "base": {"url": str(base_remote), "branch": "dev"},
    })
    monkeypatch.setattr(maintenance, "_assert_origin", lambda *_: None)
    result = maintenance.pull_workflow_repos(project, [])
    assert result["mode"] == "project-pins"
    assert _git(project / ".agents", "rev-parse", "HEAD") == newer_agents
    assert _git(project / ".agents/base", "rev-parse", "HEAD") == second_base
    assert not _git(project / ".agents", "status", "--porcelain")
