"""Explicit, evidence-gated deployment operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .commands import run_command_groups
from .git import assert_safe_branch, baseline, run_git
from .io import read_json
from .model import StateStore
from .pipeline import workflow_root
from .structure import validate_deployment_evidence

_AWS_LOCAL_ENVIRONMENT_KEYS = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_PROFILE",
    "AWS_ACCOUNT_ID",
}
_AWS_KEY_PAIR = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}


def _load_local_aws_environment(project: Path) -> dict[str, str]:
    path = project / ".env"
    if not path.exists():
        return {}
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("deployment .env must be a regular file inside the project root")
    tracked_code, _ = run_git(project, "ls-files", "--error-unmatch", "--", ".env")
    if tracked_code == 0:
        raise RuntimeError("deployment .env is tracked by Git; remove it from the index first")
    ignored_code, _ = run_git(project, "check-ignore", "-q", "--", ".env")
    if ignored_code != 0:
        raise RuntimeError("deployment .env must be covered by .gitignore")

    loaded: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise RuntimeError(f"invalid .env assignment on line {line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _AWS_LOCAL_ENVIRONMENT_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if "$(" in value or "`" in value or "\x00" in value:
            raise RuntimeError(f"unsafe .env value for {key}")
        if value.startswith("<") and value.endswith(">"):
            continue
        if value and key not in os.environ:
            loaded[key] = value

    effective = {key: os.environ.get(key, loaded.get(key, "")) for key in _AWS_KEY_PAIR}
    present = {key for key, value in effective.items() if value}
    if present and present != _AWS_KEY_PAIR:
        missing = sorted(_AWS_KEY_PAIR - present)
        raise RuntimeError(f"incomplete AWS access key pair; missing {', '.join(missing)}")
    return loaded


def deployment_status(project: Path) -> dict[str, Any]:
    state = StateStore(project).load()
    evidence_root = project / ".ai" / "evidence" / "deployment"
    evidence: dict[str, Any] = {}
    for name in (
        "readiness",
        "release",
        "staging",
        "production",
        "rollback-staging",
        "rollback-production",
    ):
        value = read_json(evidence_root / f"{name}.json")
        if isinstance(value, dict):
            evidence[name] = value
    return {
        "provider": state["frameworks"].get("deployment", "unknown"),
        "phase_generated": "deployment" in state.get("completed_phases", []),
        "evidence": evidence,
    }


def _validate_operation_evidence(
    project: Path, path: Path, environment: str, operation: str
) -> dict[str, Any]:
    evidence = read_json(path)
    schema = read_json(workflow_root() / "schemas" / "deployment-operation.schema.json")
    if not isinstance(evidence, dict) or not isinstance(schema, dict):
        raise RuntimeError(f"deployment operation evidence is missing: {path}")
    errors = sorted(Draft202012Validator(schema).iter_errors(evidence), key=lambda e: list(e.path))
    if errors:
        summaries = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors
        ]
        raise RuntimeError(f"deployment operation evidence is invalid: {summaries}")
    if evidence["environment"] != environment or evidence["operation"] != operation:
        raise RuntimeError("deployment operation evidence does not match the requested operation")
    return evidence


def _validate_release(project: Path, source_commit: str) -> dict[str, Any]:
    evidence = read_json(project / ".ai" / "evidence" / "deployment" / "release.json")
    schema = read_json(workflow_root() / "schemas" / "deployment-release.schema.json")
    if not isinstance(evidence, dict) or not isinstance(schema, dict):
        raise RuntimeError("verified immutable release evidence is missing")
    errors = sorted(Draft202012Validator(schema).iter_errors(evidence), key=lambda e: list(e.path))
    if errors:
        summaries = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors
        ]
        raise RuntimeError(f"deployment release evidence is invalid: {summaries}")
    if evidence["source_commit"] != source_commit:
        raise RuntimeError("deployment release evidence does not match the current source commit")
    return evidence


def execute_operation(
    project: Path,
    environment: str,
    operation: str,
    execute: bool,
    approved: bool,
) -> dict[str, Any]:
    if environment not in {"staging", "production"} or operation not in {"deploy", "rollback"}:
        raise RuntimeError("unsupported deployment operation")
    state = StateStore(project).load()
    if state["frameworks"].get("deployment") != "aws":
        raise RuntimeError("AWS deployment is not selected")
    if "deployment" not in state.get("completed_phases", []):
        raise RuntimeError("run start-deployment and pass its readiness gate first")
    validate_deployment_evidence(
        project, workflow_root() / "schemas" / "deployment-readiness.schema.json"
    )
    current = baseline(project)
    branch = current["branch"] if isinstance(current["branch"], str) else None
    assert_safe_branch(branch)
    if branch != state.get("git", {}).get("branch"):
        raise RuntimeError("deployment branch does not match the verified workflow branch")
    if current["dirty"]:
        raise RuntimeError("deployment requires a clean verified source tree")
    source_commit = current["baseline_commit"]
    if not isinstance(source_commit, str):
        raise RuntimeError("deployment requires a committed source revision")
    release = _validate_release(project, source_commit)
    if environment == "production" and not approved:
        raise RuntimeError("production operations require --approve-production")
    if operation == "rollback" and not approved:
        raise RuntimeError("rollback requires explicit --approve-rollback")
    if environment == "production" and operation == "deploy":
        staging = _validate_operation_evidence(
            project,
            project / ".ai" / "evidence" / "deployment" / "staging.json",
            "staging",
            "deploy",
        )
        if not staging["verified"]:
            raise RuntimeError("the staging release is not verified")
    group = f"{operation}-{environment}"
    if not execute:
        return {
            "status": "READY",
            "operation": operation,
            "environment": environment,
            "command_group": group,
            "note": "Dry run only; explicit execution authorization is still required.",
        }
    local_environment = _load_local_aws_environment(project)
    if local_environment:
        run_command_groups(project, [group], environment=local_environment)
    else:
        run_command_groups(project, [group])
    evidence_name = environment if operation == "deploy" else f"rollback-{environment}"
    evidence = _validate_operation_evidence(
        project,
        project / ".ai" / "evidence" / "deployment" / f"{evidence_name}.json",
        environment,
        operation,
    )
    if evidence["source_commit"] != source_commit:
        raise RuntimeError("deployment evidence does not match the deployed source commit")
    if evidence["artifact_digest"] != release["artifact_digest"]:
        raise RuntimeError("deployment did not use the verified immutable release digest")
    if environment == "production" and operation == "deploy":
        staging = read_json(project / ".ai" / "evidence" / "deployment" / "staging.json")
        if (
            not isinstance(staging, dict)
            or evidence["artifact_digest"] != staging["artifact_digest"]
        ):
            raise RuntimeError("production did not promote the staging-verified artifact digest")
    return {"status": "VERIFIED", "evidence": evidence}
