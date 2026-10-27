"""User-invoked commit and push commands, separate from verified build delivery."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .git import baseline, run_git

_REMOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SENSITIVE = re.compile(
    r"(^|/)(\.env(?:\..*)?|id_(?:rsa|ed25519)|.*\.(?:pem|p12|pfx|key)|"
    r"credentials\.json|service.account[^/]*\.json)$",
    re.I,
)


def _git(project: Path, *args: str) -> str:
    code, output = run_git(project, *args)
    if code:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {output}")
    return output


def _changed_paths(project: Path) -> list[str]:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is unavailable")
    completed = subprocess.run(  # noqa: S603 - fixed git executable and arguments
        [executable, "-C", str(project), "status", "--porcelain=v1", "--untracked-files=all", "-z"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(f"git status failed: {completed.stderr.strip()}")
    raw = completed.stdout
    entries = raw.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        if len(entry) < 4 or entry[2] != " ":
            raise RuntimeError("cannot parse Git working-tree status")
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            index += 1  # porcelain -z has a second path for rename/copy records
        index += 1
    return paths


def _assert_repository(project: Path, requested_branch: str | None) -> tuple[str, list[str]]:
    git = baseline(project)
    if not git["is_repository"]:
        raise RuntimeError("project is not a Git repository")
    root = Path(_git(project, "rev-parse", "--show-toplevel")).resolve()
    if root != project.resolve():
        raise RuntimeError(f"project must be the Git repository root: {root}")
    branch = git["branch"]
    if not isinstance(branch, str) or not branch:
        raise RuntimeError("cannot commit or push from a detached HEAD")
    _git(project, "check-ref-format", "--branch", branch)
    if requested_branch and requested_branch != branch:
        raise RuntimeError(
            f"requested branch {requested_branch!r} differs from current branch {branch!r}; "
            "switch branches explicitly before running this command"
        )
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        marker_path = Path(_git(project, "rev-parse", "--git-path", marker))
        if not marker_path.is_absolute():
            marker_path = project / marker_path
        if marker_path.exists():
            raise RuntimeError(f"finish the in-progress Git operation first: {marker}")
    for directory in ("rebase-merge", "rebase-apply"):
        directory_path = Path(_git(project, "rev-parse", "--git-path", directory))
        if not directory_path.is_absolute():
            directory_path = project / directory_path
        if directory_path.exists():
            raise RuntimeError("finish the in-progress Git rebase first")
    unmerged = _git(project, "diff", "--name-only", "--diff-filter=U")
    if unmerged:
        raise RuntimeError("resolve unmerged files before committing")
    paths = _changed_paths(project)
    sensitive = [
        path for path in paths
        if _SENSITIVE.search(path) and not path.endswith(".env.example")
    ]
    if sensitive:
        raise RuntimeError(
            "potential secret files need review before staging: " + ", ".join(sensitive)
        )
    return branch, paths


def _message(paths: list[str], supplied: str | None) -> str:
    if supplied is not None:
        subject = supplied.splitlines()[0].strip() if supplied.splitlines() else ""
        if not subject or len(subject) > 72 or any(ord(char) < 32 for char in subject):
            raise RuntimeError(
                "commit subject must be nonempty, one line, and at most 72 characters"
            )
        return supplied
    if all(path.endswith((".md", ".rst")) for path in paths):
        return "docs: update project documentation"
    if all(path.startswith("tests/") or "/tests/" in path for path in paths):
        return "test: update project checks"
    if any(path.startswith(".agents/") for path in paths):
        return "chore(workflow): update project automation"
    if any(path.startswith("apps/backend/") for path in paths):
        return "chore(backend): update application code"
    if any(path.startswith("apps/frontend/") for path in paths):
        return "chore(frontend): update application code"
    return "chore: update project files"


def _assert_remote_ready(project: Path, remote: str, branch: str) -> None:
    if not _REMOTE.fullmatch(remote):
        raise RuntimeError("remote must be a configured Git remote name")
    url = _git(project, "remote", "get-url", remote)
    if not url:
        raise RuntimeError(f"Git remote is not configured: {remote}")
    ref = f"refs/heads/{branch}"
    remote_head = _git(project, "ls-remote", "--heads", remote, ref)
    if remote_head:
        _git(project, "fetch", "--no-tags", remote, ref)
        head_code, _ = run_git(project, "rev-parse", "--verify", "HEAD")
        if head_code:
            raise RuntimeError("remote branch already exists; local branch has no baseline commit")
        ancestor, _ = run_git(project, "merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD")
        if ancestor:
            raise RuntimeError(
                "remote branch has commits missing locally; fetch and reconcile before pushing"
            )



def commit_or_push(
    project: Path,
    *,
    push: bool,
    branch: str | None = None,
    remote: str = "origin",
    message: str | None = None,
) -> dict[str, Any]:
    """Preflight, commit current work when present, and optionally push current branch."""
    current, paths = _assert_repository(project, branch)
    if push:
        _assert_remote_ready(project, remote, current)
    committed = False
    if paths:
        subject = _message(paths, message)
        _git(project, "diff", "--check")
        _git(project, "diff", "--cached", "--check")
        _git(project, "add", "-A")
        _git(project, "diff", "--cached", "--check")
        staged = _git(project, "diff", "--cached", "--name-only", "-z")
        if not staged:
            raise RuntimeError("Git reported changes but nothing was staged")
        _git(project, "commit", "-m", subject)
        committed = True
        remaining = _changed_paths(project)
        if remaining:
            raise RuntimeError(
                "commit completed but Git hooks left uncommitted changes; review before pushing"
            )
    elif not push:
        return {"status": "clean", "branch": current, "committed": False, "pushed": False}
    head = _git(project, "rev-parse", "HEAD")
    if push:
        _git(project, "push", "--set-upstream", remote, f"HEAD:refs/heads/{current}")
    return {
        "status": "pushed" if push else "committed",
        "branch": current,
        "commit": head,
        "committed": committed,
        "pushed": push,
        "remote": remote if push else None,
    }
