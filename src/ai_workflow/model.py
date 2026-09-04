"""Workflow model helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .io import read_json, write_json

PHASES = (
    "bootstrap",
    "requirements",
    "design",
    "frontend",
    "mobile",
    "backend",
    "integration",
    "testing",
    "deployment",
    "delivery",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class StateStore:
    def __init__(self, project: Path) -> None:
        self.project = project.resolve()
        self.path = self.project / ".ai" / "state.json"

    def load(self) -> dict[str, Any]:
        state = read_json(self.path)
        if not isinstance(state, dict):
            raise RuntimeError(f"workflow is not initialized: {self.project}")
        frameworks = state.get("frameworks")
        if isinstance(frameworks, dict):
            frameworks.setdefault("deployment", "unknown")
        capabilities = state.setdefault("capabilities", {})
        if isinstance(capabilities, dict):
            capabilities.setdefault("rag", False)
        return state

    def save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json(self.path, state)

    def create(
        self,
        project_id: str,
        mode: str,
        frontend: str,
        backend: str,
        baseline: str | None,
        branch: str | None,
        assumptions: list[str],
        mobile: str = "unknown",
        deployment: str = "unknown",
        capabilities: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        if self.path.exists():
            raise RuntimeError("workflow state already exists; use ai status or ai resume")
        state = {
            "workflow_version": "1.0.0",
            "project_id": project_id,
            "mode": mode,
            "status": "initialized",
            "current_phase": "bootstrap",
            "frameworks": {
                "frontend": frontend,
                "mobile": mobile,
                "backend": backend,
                "deployment": deployment,
            },
            "capabilities": capabilities or {"rag": False, "webscraping": False},
            "git": {"baseline_commit": baseline, "branch": branch},
            "features": {},
            "assumptions": assumptions,
            "updated_at": utc_now(),
        }
        self.save(state)
        write_json(self.project / ".ai" / "task-queue.json", {"version": 1, "tasks": []})
        write_json(self.project / ".ai" / "path-leases.json", {"version": 1, "leases": []})
        (self.project / ".ai" / "decisions.jsonl").touch(exist_ok=True)
        for directory in ("logs", "evidence", "discovery", "knowledge"):
            (self.project / ".ai" / directory).mkdir(parents=True, exist_ok=True)
        return state
