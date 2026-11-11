"""A repaired node must keep handling new findings in the same invocation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ai_workflow.execution as execution


def _run_frontend_with_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, findings: list[str | None]
) -> tuple[int, int]:
    workflow = tmp_path / "workflow"
    (workflow / "blueprints").mkdir(parents=True)
    (workflow / "config").mkdir()
    (tmp_path / ".ai").mkdir()
    (workflow / "blueprints/frontend.json").write_text(json.dumps({
        "nodes": [{
            "id": "verify-frontend", "type": "agentic", "agent": "verifier",
            "required_output": ".ai/evidence/frontend-verification.json",
            "verification": "verified-true",
        }],
    }))
    (workflow / "config/pipeline.json").write_text(json.dumps({
        "execution": {
            "maximum_retries_per_failure": 0,
            "maximum_distinct_recoveries_per_node": 6,
        },
    }))
    state = {"frameworks": {}, "status": "running", "completed_phases": []}

    class Store:
        def __init__(self, _project: Path) -> None:
            pass

        def load(self) -> dict:
            return state

        def save(self, _state: dict) -> None:
            pass

    monkeypatch.setattr(execution, "StateStore", Store)
    monkeypatch.setattr(execution, "workflow_root", lambda: workflow)
    monkeypatch.setattr(execution, "phase_tasks", lambda tasks, _phase: tasks)
    monkeypatch.setattr(execution, "_phase_verification_current", lambda *_: False)
    monkeypatch.setattr(execution, "_node_input_files", lambda *_: [])
    monkeypatch.setattr(execution, "_skill_paths", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(execution, "_prompt", lambda *_: (
        "run", {"task_id": "test", "allowed_paths": ["apps/frontend/**"],
                "forbidden_paths": [".agents/**"]},
    ))
    monkeypatch.setattr(execution, "_acquire_path_lease", lambda *_: None)
    monkeypatch.setattr(execution, "_release_path_lease", lambda *_: None)
    monkeypatch.setattr(execution, "record_attempt", lambda *_, **__: None)
    monkeypatch.setattr(execution, "_evidence_format_errors", lambda *_: [])
    monkeypatch.setattr(execution, "_artifact_external_blocker", lambda *_: None)
    monkeypatch.setattr(execution, "try_track_build_issue", lambda *_, **__: None)
    monkeypatch.setattr(execution, "resolve_build_issues", lambda *_, **__: None)
    monkeypatch.setattr(execution, "resolve_matching_build_issues", lambda *_, **__: None)
    monkeypatch.setattr(execution, "_record_failure", lambda *_, **__: None)
    monkeypatch.setattr(execution, "_validate_semantic_artifacts", lambda *_: None)
    monkeypatch.setattr(execution, "evaluate_phase_gate", lambda *_: {"passed": True})
    monkeypatch.setattr(execution, "_artifact_ok", lambda path, _verification: (
        path.is_file() and json.loads(path.read_text()).get("verified") is True
    ))
    attempts = 0
    recoveries = 0

    def adapter(_project: Path, _adapter: str, _prompt: str) -> dict:
        nonlocal attempts
        finding = findings[attempts]
        attempts += 1
        output = tmp_path / ".ai/evidence/frontend-verification.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "verified": finding is None,
            "reviews": [] if finding is None else [
                {"status": "failed", "details": finding}
            ],
        }))
        return {"returncode": 0, "stderr_tail": "", "stdout_tail": ""}

    def recover(*_args: object) -> tuple[bool, str]:
        nonlocal recoveries
        recoveries += 1
        return True, "focused source repair passed"

    monkeypatch.setattr(execution, "_run_adapter", adapter)
    monkeypatch.setattr(execution, "_run_final_project_recovery", recover)
    execution._execute_phase_unlocked(tmp_path, "frontend", "test", [])
    return attempts, recoveries


def test_distinct_findings_recover_without_restarting_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run_frontend_with_findings(
        tmp_path, monkeypatch, ["first defect", "second defect", None]
    ) == (3, 2)


def test_identical_finding_stops_repeated_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RuntimeError, match="same finding remained"):
        _run_frontend_with_findings(
            tmp_path, monkeypatch, ["unchanged defect", "unchanged defect"]
        )
