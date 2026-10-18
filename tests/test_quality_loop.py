import json
from pathlib import Path

import pytest

from ai_workflow.cli import main
from ai_workflow.execution import _prompt
from ai_workflow.io import append_jsonl, write_json
from ai_workflow.quality_loop import (
    approve_lesson,
    approved_guidance,
    evaluate_manifest,
    propose_lessons,
    record_attempt,
)


def _run(project: Path, adapter: str, *, verified: bool = True) -> None:
    project.mkdir()
    (project / "PRD.md").write_text("# Same product\n", encoding="utf-8")
    write_json(
        project / ".ai" / "state.json",
        {
            "assumptions": ["PRD source: PRD.md"],
            "frameworks": {"frontend": "react"},
            "capabilities": {"rag": False},
        },
    )
    write_json(
        project / ".ai" / "node-state.json",
        {"nodes": {"frontend/verify/phase": {"status": "VERIFIED" if verified else "FAILED"}}},
    )
    record_attempt(
        project,
        identity="frontend/verify/phase",
        adapter=adapter,
        agent="verifier",
        skills=["skill-a"],
        prompt="secret prompt",
        elapsed_ms=12,
        result={"returncode": 0, "stdout_tail": "secret output"},
    )


def test_telemetry_contains_no_prompt_or_adapter_output(tmp_path: Path) -> None:
    _run(tmp_path / "codex", "codex")
    text = (tmp_path / "codex" / ".ai/telemetry/attempts.jsonl").read_text()
    assert "secret prompt" not in text
    assert "secret output" not in text
    row = json.loads(text)
    assert row["prompt_characters"] == len("secret prompt")
    assert row["reported_usage"] is None


def test_evaluate_matching_runs_and_reject_mismatch(tmp_path: Path) -> None:
    _run(tmp_path / "codex", "codex")
    _run(tmp_path / "claude", "claude")
    manifest = tmp_path / "comparison.json"
    write_json(
        manifest,
        {
            "cases": [
                {
                    "id": "small-prd",
                    "required_nodes": ["frontend/verify/phase"],
                    "runs": [
                        {"adapter": "codex", "project": "codex"},
                        {"adapter": "claude", "project": "claude"},
                    ],
                }
            ]
        },
    )
    report = evaluate_manifest(manifest)
    assert report["all_checkpoint_parity"] is True
    assert report["cases"][0]["runs"][0]["prompt_characters"] == len("secret prompt")
    assert main(["evaluate-adapters", "--manifest", str(manifest)]) == 0
    (tmp_path / "claude/PRD.md").write_text("# Different product\n", encoding="utf-8")
    assert evaluate_manifest(manifest)["all_comparable"] is False
    assert main(["evaluate-adapters", "--manifest", str(manifest)]) == 2


def test_evaluation_rejects_empty_or_mislabeled_runs(tmp_path: Path) -> None:
    _run(tmp_path / "codex", "codex", verified=False)
    _run(tmp_path / "claude", "claude", verified=False)
    manifest = tmp_path / "comparison.json"
    write_json(
        manifest,
        {
            "cases": [
                {
                    "required_nodes": ["frontend/verify/phase"],
                    "runs": [
                        {"adapter": "codex", "project": "codex"},
                        {"adapter": "claude", "project": "claude"},
                    ]
                }
            ]
        },
    )
    assert evaluate_manifest(manifest)["all_checkpoint_parity"] is False
    append_jsonl(tmp_path / "claude/.ai/telemetry/attempts.jsonl", {"adapter": "codex"})
    assert evaluate_manifest(manifest)["all_comparable"] is False


def test_learning_requires_explicit_approval_and_is_phase_scoped(tmp_path: Path) -> None:
    append_jsonl(
        tmp_path / ".ai/failures.jsonl",
        {
            "failure_id": "FAIL-1",
            "task_id": "backend/verify/phase",
            "failure_class": "agent-or-artifact-failure",
            "root_cause": "secret diagnostic",
        },
    )
    proposals = propose_lessons(tmp_path)
    assert len(proposals) == 1
    assert approved_guidance(tmp_path, "backend") == []
    with pytest.raises(ValueError, match="one line"):
        approve_lesson(tmp_path, proposals[0]["id"], "unsafe\ntext")
    lesson = approve_lesson(tmp_path, proposals[0]["id"], "Check the verification contract first.")
    assert lesson["phase"] == "backend"
    assert approved_guidance(tmp_path, "backend") == ["Check the verification contract first."]
    assert approved_guidance(tmp_path, "frontend") == []
    assert "secret diagnostic" not in (tmp_path / ".ai/learning/proposals.json").read_text()
    assert propose_lessons(tmp_path)[0]["status"] == "approved"


def test_only_approved_phase_lessons_enter_prompt(tmp_path: Path) -> None:
    write_json(tmp_path / ".ai/learning/approved.json", {
        "lessons": [
            {"phase": "requirements", "guidance": "Check requirement identifiers."},
            {"phase": "backend", "guidance": "Do not leak this to requirements."},
        ]
    })
    node = {
        "id": "reconcile-current-state", "agent": "requirements-reconciliation-agent",
        "required_output": "docs/generated/requirement-reconciliation.json",
        "verification": "schema",
    }
    state = {
        "frameworks": {"frontend": "unknown", "mobile": "unknown", "desktop": "unknown",
                       "python_package": "unknown", "backend": "unknown", "deployment": "unknown"},
        "capabilities": {"rag": False, "webscraping": False}, "assumptions": [],
    }
    prompt, _ = _prompt(tmp_path, "requirements", node, state, None, [])
    assert "Check requirement identifiers." in prompt
    assert "Do not leak this to requirements." not in prompt
