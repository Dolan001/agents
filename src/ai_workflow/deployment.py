"""Explicit, evidence-gated deployment operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .commands import run_command_groups
from .git import assert_safe_branch, baseline
from .io import read_json
from .model import StateStore
from .pipeline import workflow_root
from .structure import validate_deployment_evidence


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
