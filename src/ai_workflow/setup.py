"""One-command, Codex-only project bootstrap."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .install import install_entrypoints


def _workflow_directory(project: Path, workflow_path: str) -> Path:
    relative = Path(workflow_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise RuntimeError("workflow path must be a safe relative project path")
    directory = (project / relative).resolve()
    if project not in directory.parents:
        raise RuntimeError("workflow path escapes the project")
    if not (directory / "bin" / "ai").is_file():
        raise RuntimeError(f"workflow launcher is missing: {directory / 'bin' / 'ai'}")
    return directory


def _run_git(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is required for project setup")
    return subprocess.run(  # noqa: S603 - resolved executable and fixed argument forms
        [git, "-C", str(project), *arguments],
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )


def _initialize_submodules(project: Path, workflow_path: str, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"status": "skipped", "reason": "disabled by --skip-submodules"}
    if not shutil.which("git"):
        return {"status": "skipped", "reason": "Git is unavailable"}
    repository = _run_git(project, "rev-parse", "--show-toplevel")
    if repository.returncode != 0:
        return {"status": "skipped", "reason": "project is not a Git repository"}
    registered = _run_git(project, "submodule", "status", "--", workflow_path)
    if registered.returncode != 0 or not registered.stdout.strip():
        return {"status": "skipped", "reason": "workflow path is not a registered submodule"}
    updated = _run_git(project, "submodule", "update", "--init", "--recursive", "--", workflow_path)
    if updated.returncode != 0:
        detail = updated.stderr.strip()[-1000:] or "unknown Git error"
        raise RuntimeError(f"submodule initialization failed: {detail}")
    return {"status": "initialized", "path": workflow_path}


def _prd_readiness(project: Path) -> dict[str, Any]:
    candidates: list[Path] = []
    identities: set[tuple[int, int]] = set()
    for relative in ("docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md"):
        candidate = project / relative
        if not candidate.is_file():
            continue
        metadata = candidate.stat()
        identity = (metadata.st_dev, metadata.st_ino)
        if identity not in identities:
            candidates.append(candidate)
            identities.add(identity)
    if not candidates:
        return {
            "status": "missing",
            "accepted_paths": ["docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md"],
        }
    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "paths": [path.relative_to(project).as_posix() for path in candidates],
        }
    path = candidates[0]
    if not path.read_text(encoding="utf-8").strip():
        return {"status": "empty", "path": path.relative_to(project).as_posix()}
    return {"status": "ready", "path": path.relative_to(project).as_posix()}


def _exclude_generated_skills(project: Path) -> dict[str, str]:
    if not shutil.which("git"):
        return {"status": "skipped", "reason": "Git is unavailable"}
    repository = _run_git(project, "rev-parse", "--show-toplevel")
    if repository.returncode != 0:
        return {"status": "skipped", "reason": "project is not a Git repository"}
    ignored = _run_git(project, "check-ignore", "-q", "--", ".agents")
    if ignored.returncode == 0:
        return {"status": "already-ignored", "path": ".agents/"}
    git_path = _run_git(project, "rev-parse", "--git-path", "info/exclude")
    if git_path.returncode != 0 or not git_path.stdout.strip():
        raise RuntimeError("unable to resolve the local Git exclude file")
    exclude = Path(git_path.stdout.strip())
    if not exclude.is_absolute():
        exclude = project / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    marker = "# ai_workflow generated Codex skills\n/.agents/\n"
    separator = "" if not existing or existing.endswith("\n") else "\n"
    exclude.write_text(existing + separator + marker, encoding="utf-8")
    return {"status": "locally-excluded", "path": ".agents/"}


def setup_project(
    project: Path,
    workflow_path: str = "ai_workflow",
    force: bool = False,
    initialize_submodules: bool = True,
) -> dict[str, Any]:
    """Bootstrap Codex discovery without creating workflow runtime state."""
    _workflow_directory(project, workflow_path)
    submodules = _initialize_submodules(project, workflow_path, initialize_submodules)
    installation = install_entrypoints(project, workflow_path, force, ("codex",))
    git_exclude = _exclude_generated_skills(project)
    prd = _prd_readiness(project)
    toolchain: dict[str, dict[str, Any]] = {
        "python": {
            "available": True,
            "version": ".".join(str(item) for item in sys.version_info[:3]),
            "supported": sys.version_info >= (3, 12),
        },
        "git": {"available": shutil.which("git") is not None},
        "codex": {"available": shutil.which("codex") is not None},
    }
    if not toolchain["python"]["supported"]:
        next_action = "install Python 3.12 or newer, then rerun setup"
    elif not toolchain["git"]["available"]:
        next_action = "install Git, then rerun setup"
    elif not toolchain["codex"]["available"]:
        next_action = "install Codex, then rerun setup"
    elif prd["status"] != "ready":
        next_action = "add exactly one non-empty PRD.md or docs/PRD.md"
    else:
        next_action = (
            "reopen Codex, then run $start-build --frontend <react|nextjs> "
            "--backend <django-drf|fastapi> --github-user <user>"
        )
    return {
        "status": "installed",
        "platform": "codex",
        "workflow_path": workflow_path,
        "submodules": submodules,
        "git_exclude": git_exclude,
        "toolchain": toolchain,
        "prd": prd,
        "skills": installation["commands"],
        "installed": installation["installed"],
        "unchanged": installation["unchanged"],
        "runtime_state_created": False,
        "next_action": next_action,
    }
