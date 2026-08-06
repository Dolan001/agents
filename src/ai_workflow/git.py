"""Read-only Git inspection and fail-closed release checks."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PROTECTED = {"main", "master", "dev", "develop", "stage", "staging", "production", "prod"}
SAFE = re.compile(r"^ai/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")


def run_git(project: Path, *arguments: str) -> tuple[int, str]:
    git = shutil.which("git")
    if not git:
        return 127, "git executable is unavailable"
    completed = subprocess.run(  # noqa: S603 - fixed executable and adapter-owned arguments
        [git, "-C", str(project), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, (completed.stdout or completed.stderr).strip()


def baseline(project: Path) -> dict[str, object]:
    inside_code, inside = run_git(project, "rev-parse", "--is-inside-work-tree")
    if inside_code != 0 or inside != "true":
        return {
            "is_repository": False,
            "baseline_commit": None,
            "branch": None,
            "dirty": False,
            "changes": [],
        }
    _, commit = run_git(project, "rev-parse", "HEAD")
    _, branch = run_git(project, "branch", "--show-current")
    _, status = run_git(project, "status", "--porcelain")
    return {
        "is_repository": True,
        "baseline_commit": commit or None,
        "branch": branch or None,
        "dirty": bool(status),
        "changes": status.splitlines(),
    }


def assert_safe_branch(branch: str | None) -> None:
    if not branch:
        raise RuntimeError("a named Git branch is required")
    if branch in PROTECTED:
        raise RuntimeError(f"protected branch is read-only: {branch}")
    if not SAFE.fullmatch(branch):
        raise RuntimeError("branch must match ai/<github-user>/<feature-slug>")
