"""Read-only Git inspection and fail-closed release checks."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from .io import read_json

PROTECTED = {"main", "master", "dev", "develop", "stage", "staging", "production", "prod"}
SAFE = re.compile(r"^ai/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")


def _matches(relative: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return relative == pattern[:-3] or relative.startswith(pattern[:-2])
    return PurePosixPath(relative).match(pattern)


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
    commit_code, commit = run_git(project, "rev-parse", "HEAD")
    branch_code, branch = run_git(project, "branch", "--show-current")
    _, status = run_git(project, "status", "--porcelain")
    return {
        "is_repository": True,
        "baseline_commit": commit if commit_code == 0 and commit else None,
        "branch": branch if branch_code == 0 and branch else None,
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


def prepare_feature_branch(project: Path, github_user: str, feature: str) -> str:
    user_slug = re.sub(r"[^a-z0-9]+", "-", github_user.lower()).strip("-")
    feature_slug = re.sub(r"[^a-z0-9]+", "-", feature.lower()).strip("-")
    desired = f"ai/{user_slug}/{feature_slug}"
    assert_safe_branch(desired)
    current = baseline(project)
    if not current["is_repository"]:
        code, output = run_git(project, "init")
        if code != 0:
            raise RuntimeError(f"failed to initialize Git: {output}")
        current = baseline(project)
    branch = current["branch"] if isinstance(current["branch"], str) else None
    if branch and branch not in PROTECTED:
        assert_safe_branch(branch)
        return branch
    code, output = run_git(project, "switch", "-c", desired)
    if code != 0:
        raise RuntimeError(f"failed to create feature branch {desired}: {output}")
    return desired


def commit_verified_feature(
    project: Path, task: dict[str, object], push: bool
) -> dict[str, object]:
    feature_id = str(task["feature_id"])
    evidence_path = (
        project / ".ai" / "evidence" / "features" / feature_id / "final-verification.json"
    )
    evidence = read_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        raise RuntimeError(f"feature is not independently verified: {feature_id}")
    changed_files = evidence.get("changed_files")
    if (
        not isinstance(changed_files, list)
        or not changed_files
        or not all(isinstance(item, str) for item in changed_files)
    ):
        raise RuntimeError(f"verified evidence lacks changed_files: {feature_id}")
    allowed = task.get("allowed_paths")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise RuntimeError(f"task has invalid allowed_paths: {feature_id}")
    for relative in changed_files:
        candidate = (project / relative).resolve()
        if candidate != project and project not in candidate.parents:
            raise RuntimeError(f"verified changed file escapes project: {relative}")
        if not any(_matches(relative, pattern) for pattern in allowed):
            raise RuntimeError(f"verified changed file is outside task scope: {relative}")
    git = baseline(project)
    branch = git["branch"] if isinstance(git["branch"], str) else None
    assert_safe_branch(branch)
    if branch is None:  # Narrow the type after the fail-closed assertion.
        raise RuntimeError("a named Git branch is required")
    code, output = run_git(project, "add", "--", *changed_files)
    if code != 0:
        raise RuntimeError(f"failed to stage verified feature {feature_id}: {output}")
    staged_code, _ = run_git(project, "diff", "--cached", "--quiet")
    if staged_code == 0:
        raise RuntimeError(f"verified feature has no uncommitted scoped changes: {feature_id}")
    requirement_ids = task.get("requirement_ids")
    if not isinstance(requirement_ids, list):
        raise RuntimeError(f"task has invalid requirement_ids: {feature_id}")
    requirements = ", ".join(str(item) for item in requirement_ids)
    message = (
        f"feat({feature_id}): deliver verified feature\n\n"
        f"Requirements: {requirements}\n"
        "Tests: recorded in final-verification.json\n"
        "Verification: independent\n"
    )
    code, output = run_git(project, "commit", "-m", message)
    if code != 0:
        raise RuntimeError(f"failed to commit verified feature {feature_id}: {output}")
    _, commit = run_git(project, "rev-parse", "HEAD")
    if push:
        code, output = run_git(project, "push", "--set-upstream", "origin", branch)
        if code != 0:
            raise RuntimeError(f"failed to push verified feature {feature_id}: {output}")
    return {"feature_id": feature_id, "commit": commit, "branch": branch, "pushed": push}
