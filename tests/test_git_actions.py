import shutil
import subprocess
from pathlib import Path

import pytest

from ai_workflow.cli import main
from ai_workflow.git_actions import commit_or_push

GIT = shutil.which("git")
assert GIT is not None


def git(project: Path, *args: str) -> str:
    completed = subprocess.run(  # noqa: S603 - test-owned Git arguments
        [GIT, "-C", str(project), *args], capture_output=True, text=True, check=True,
    )
    return completed.stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    remote = tmp_path / "remote.git"
    project.mkdir()
    git(project, "init", "-b", "feature/chat")
    git(project, "config", "user.name", "Workflow Test")
    git(project, "config", "user.email", "workflow@example.test")
    git(project, "commit", "--allow-empty", "-m", "chore: initialize")
    subprocess.run(  # noqa: S603 - test-owned bare repository
        [GIT, "init", "--bare", str(remote)], check=True, capture_output=True
    )
    git(project, "remote", "add", "origin", str(remote))
    return project, remote


def test_commit_only_preserves_branch_and_uses_supplied_message(tmp_path: Path) -> None:
    project, remote = repository(tmp_path)
    (project / "README.md").write_text("Project\n", encoding="utf-8")
    result = commit_or_push(
        project, push=False, branch="feature/chat", message="docs: explain the project",
    )
    assert result["status"] == "committed" and result["pushed"] is False
    assert git(project, "log", "-1", "--format=%s") == "docs: explain the project"
    assert git(project, "branch", "--show-current") == "feature/chat"
    assert not git(remote, "branch", "--list", "feature/chat")


def test_push_commits_if_needed_and_reuses_existing_commit(tmp_path: Path) -> None:
    project, remote = repository(tmp_path)
    (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
    first = commit_or_push(project, push=True, message="feat: add application entry point")
    assert first["committed"] is True and first["pushed"] is True
    assert git(remote, "rev-parse", "refs/heads/feature/chat") == first["commit"]
    second = commit_or_push(project, push=True)
    assert second["committed"] is False and second["commit"] == first["commit"]


def test_preflight_rejects_mismatched_branch_and_secret_file(tmp_path: Path) -> None:
    project, _ = repository(tmp_path)
    (project / ".env.local").write_text("SECRET=example\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="differs from current branch"):
        commit_or_push(project, push=False, branch="main")
    with pytest.raises(RuntimeError, match="potential secret files"):
        commit_or_push(project, push=False)
    assert git(project, "log", "-1", "--format=%s") == "chore: initialize"


def test_stale_rebase_head_does_not_block_commit(tmp_path: Path) -> None:
    project, _ = repository(tmp_path)
    git_path = Path(git(project, "rev-parse", "--git-path", "REBASE_HEAD"))
    if not git_path.is_absolute():
        git_path = project / git_path
    git_path.write_text("stale\n", encoding="utf-8")
    (project / "README.md").write_text("Project\n", encoding="utf-8")
    assert commit_or_push(project, push=False)["committed"] is True


def test_push_checks_remote_divergence_before_local_commit(tmp_path: Path) -> None:
    project, remote = repository(tmp_path)
    other = tmp_path / "other"
    subprocess.run(  # noqa: S603 - test-owned local clone
        [GIT, "clone", str(remote), str(other)], check=True, capture_output=True
    )
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.test")
    git(project, "push", "-u", "origin", "feature/chat")
    git(other, "fetch", "origin", "feature/chat")
    git(other, "switch", "-c", "feature/chat", "FETCH_HEAD")
    (other / "remote.txt").write_text("new remote commit\n", encoding="utf-8")
    git(other, "add", "remote.txt")
    git(other, "commit", "-m", "docs: update remote")
    git(other, "push", "origin", "feature/chat")
    (project / "local.txt").write_text("uncommitted local change\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="commits missing locally"):
        commit_or_push(project, push=True)
    assert git(project, "log", "-1", "--format=%s") == "chore: initialize"


def test_user_facing_git_commit_command_works_without_workflow_state(tmp_path: Path) -> None:
    project, _ = repository(tmp_path)
    (project / "README.md").write_text("Project\n", encoding="utf-8")
    assert main([
        "git-commit", "feature/chat", "--project", str(project),
        "--message", "docs: describe the project",
    ]) == 0
    assert git(project, "log", "-1", "--format=%s") == "docs: describe the project"
