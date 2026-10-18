"""Read-only, checkpoint-based workflow progress estimates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .execution import (
    _artifact_ok,
    _inside,
    _node_input_files,
    _required_exists,
    phase_checkpoint_current,
)
from .io import read_json
from .model import PHASES, StateStore
from .pipeline import node_cache_key, workflow_root
from .task_projection import phase_tasks


def _enabled(frameworks: dict[str, str], phase: str) -> bool:
    if phase == "deployment":
        return frameworks.get("deployment", "unknown") != "unknown"
    if phase == "desktop":
        return any(
            frameworks.get(side, "unknown") != "unknown"
            for side in ("desktop", "python_package")
        )
    if phase == "design":
        return not (
            frameworks.get("python_package", "unknown") != "unknown"
            and all(
                frameworks.get(side, "unknown") == "unknown"
                for side in ("frontend", "mobile", "desktop")
            )
        )
    return (
        phase not in {"frontend", "mobile", "backend"}
        or frameworks.get(phase, "unknown") != "unknown"
    )


def _node_current(
    project: Path, phase: str, node: dict[str, Any], feature: dict[str, Any] | None,
    checkpoints: dict[str, Any],
) -> bool:
    feature_id = feature["feature_id"] if feature else "phase"
    identity = f"{phase}/{node['id']}/{feature_id}"
    checkpoint = checkpoints.get(identity, {})
    if not isinstance(checkpoint, dict) or checkpoint.get("status") != "VERIFIED":
        return False
    output = node["required_output"].format(feature_id=feature_id)
    if not _artifact_ok(_inside(project, output), node["verification"]):
        return False
    if node.get("fanout"):
        return True
    inputs = [
        path for path in _node_input_files(project, phase, node["id"], feature)
        if path != output
    ]
    return checkpoint.get("cache_key") == node_cache_key(project, identity, inputs)


def progress_snapshot(project: Path, scope: str = "overall") -> dict[str, Any]:
    """Count current verified agent artifacts and accepted phase gates.

    The task plan fixes fanout cardinality. Before it exists, a percentage would imply
    precision that the workflow does not yet have.
    """
    state = StateStore(project).load()
    queue = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
    tasks = queue.get("tasks", []) if isinstance(queue, dict) else []
    if not isinstance(tasks, list) or not tasks:
        return {
            "scope": scope,
            "status": "planning",
            "percent": None,
            "completed_units": 0,
            "total_units": None,
            "phases": [],
        }
    frameworks = state.get("frameworks", {})
    if scope == "overall":
        phases = [
            phase for phase in PHASES
            if phase != "deployment" and _enabled(frameworks, phase)
        ]
    else:
        if scope not in PHASES:
            raise ValueError(f"unknown progress scope: {scope}")
        phases = [scope] if _enabled(frameworks, scope) else []
    node_state = read_json(project / ".ai" / "node-state.json", {"nodes": {}})
    checkpoints = node_state.get("nodes", {}) if isinstance(node_state, dict) else {}
    if not isinstance(checkpoints, dict):
        checkpoints = {}
    completed = set(state.get("completed_phases", []))
    details = []
    total = done = 0
    for phase in phases:
        if phase == "bootstrap":
            phase_total, phase_done = 1, int(phase in completed)
        else:
            blueprint = read_json(workflow_root() / "blueprints" / f"{phase}.json", {})
            nodes = blueprint.get("nodes", []) if isinstance(blueprint, dict) else []
            units = [
                (node, feature)
                for node in nodes if node.get("type") == "agentic"
                for feature in (phase_tasks(tasks, phase) if node.get("fanout") else [None])
            ]
            phase_total = len(units) + 1  # The phase gate is the final unit.
            gate = read_json(project / ".ai" / "evidence" / "gates" / f"{phase}.json", {})
            accepted = (
                phase in completed
                and isinstance(gate, dict)
                and gate.get("passed") is True
                and all(
                    _required_exists(project, pattern)
                    for pattern in gate.get("required_artifacts", [])
                )
                and phase_checkpoint_current(project, phase, tasks)
            )
            phase_done = phase_total if accepted else sum(
                _node_current(project, phase, node, feature, checkpoints)
                for node, feature in units
            )
        total += phase_total
        done += phase_done
        phase_status = (
            "complete" if phase_done == phase_total
            else "in-progress" if phase_done else "pending"
        )
        details.append({
            "phase": phase,
            "completed_units": phase_done,
            "total_units": phase_total,
            "percent": (100 * phase_done) // phase_total,
            "status": phase_status,
        })
    percent = (100 * done) // total if total else 0
    return {
        "scope": scope,
        "status": "complete" if total and done == total else "in-progress",
        "percent": percent,
        "completed_units": done,
        "total_units": total,
        "phases": details,
    }
