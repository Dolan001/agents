"""Progress is based on verified work, not wall-clock time."""

from __future__ import annotations

import json
from pathlib import Path

from ai_workflow.cli import main
from ai_workflow.io import write_json
from ai_workflow.model import StateStore
from ai_workflow.progress import progress_snapshot


def _project(tmp_path: Path) -> Path:
    StateStore(tmp_path).save({
        "project_id": "progress-test",
        "status": "running",
        "current_phase": "requirements",
        "completed_phases": ["bootstrap"],
        "frameworks": {
            "frontend": "unknown",
            "mobile": "unknown",
            "desktop": "unknown",
            "python_package": "library",
            "backend": "unknown",
            "deployment": "aws",
        },
    })
    return tmp_path


def test_progress_waits_for_task_plan(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    assert main(["status", "--project", str(project)]) == 0
    assert "progress: planning" in capsys.readouterr().out
    assert progress_snapshot(project)["percent"] is None
    assert main(["status", "--project", str(project), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["progress"]["scope"] == "overall"
    assert payload["progress"]["percent"] is None


def test_scoped_progress_requires_gate_and_fresh_checkpoints(
    tmp_path: Path, monkeypatch,
) -> None:
    project = _project(tmp_path)
    write_json(project / ".ai" / "task-queue.json", {"tasks": [{
        "task_id": "LIB-001", "feature_id": "library", "agent": "implementer",
        "allowed_paths": ["packages/python/library.py"], "depends_on": [],
    }]})
    monkeypatch.setattr("ai_workflow.progress._node_current", lambda *args: True)
    partial = progress_snapshot(project, "requirements")
    assert partial["completed_units"] == 3
    assert partial["total_units"] == 4
    assert partial["percent"] == 75

    state = StateStore(project).load()
    state["completed_phases"].append("requirements")
    StateStore(project).save(state)
    write_json(project / ".ai" / "evidence/gates/requirements.json", {"passed": True})
    monkeypatch.setattr("ai_workflow.progress.phase_checkpoint_current", lambda *args: True)
    assert progress_snapshot(project, "requirements")["percent"] == 100

    monkeypatch.setattr("ai_workflow.progress.phase_checkpoint_current", lambda *args: False)
    assert progress_snapshot(project, "requirements")["percent"] == 75

    overall = progress_snapshot(project)
    assert "deployment" not in {item["phase"] for item in overall["phases"]}
    assert "design" not in {item["phase"] for item in overall["phases"]}
    assert "frontend" not in {item["phase"] for item in overall["phases"]}
