"""Project whole-product tasks into dependency-ordered implementation phases."""

from __future__ import annotations

import fnmatch
from typing import Any


def phase_tasks(tasks: list[dict[str, Any]], phase: str) -> list[dict[str, Any]]:
    if phase not in {"frontend", "mobile", "backend"}:
        return tasks
    by_id = {task["task_id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise RuntimeError("task plan contains duplicate task IDs")
    implementations: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if "verifier" in str(task.get("agent", "")).lower() or task["task_id"].endswith("-VERIFY"):
            continue
        if task["feature_id"] in implementations:
            raise RuntimeError(f"duplicate implementation feature: {task['feature_id']}")
        implementations[task["feature_id"]] = task

    prefixes = [f"apps/{phase}/", "packages/", "docs/api/"]
    test_prefixes = {
        "frontend": ["tests/frontend/", "tests/web/", "tests/contracts/"],
        "mobile": ["tests/mobile/", "tests/contracts/"],
        "backend": [
            "tests/backend/", "tests/contracts/", "tests/rag/", "tests/security/",
            "tests/integration/",
        ],
    }
    prefixes.extend(test_prefixes[phase])

    def scoped(path: str) -> list[str]:
        if path.startswith(".ai/evidence/"):
            return [path]
        return list(dict.fromkeys(
            path if path.startswith(prefix) else prefix + "**"
            for prefix in prefixes
            if path.startswith(prefix) or fnmatch.fnmatchcase(prefix + "probe", path)
        ))

    selected = {}
    for feature, task in implementations.items():
        paths = list(dict.fromkeys(
            value for path in task.get("allowed_paths", []) for value in scoped(path)
        ))
        if not any(not path.startswith(".ai/") for path in paths):
            continue
        selected[feature] = {**task, "allowed_paths": paths}

    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def projected_dependencies(task_id: str) -> set[str]:
        dependency = by_id[task_id]
        target = selected.get(dependency["feature_id"])
        if target:
            return {target["task_id"]}
        return set().union(*(
            projected_dependencies(item) for item in dependency.get("dependencies", [])
        ))

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise RuntimeError(f"cyclic task dependency: {task_id}")
        if task_id in visited:
            return
        if task_id not in by_id:
            raise RuntimeError(f"unknown task dependency: {task_id}")
        visiting.add(task_id)
        task = by_id[task_id]
        for dependency in task.get("dependencies", []):
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)
        projected = selected.get(task["feature_id"])
        if projected and projected["task_id"] == task_id:
            # Whole-product verification dependencies are satisfied only later. The
            # current phase consumes contracts/fixtures, not invented backend proof.
            projected["description"] = (
                (
                    "Implement the backend portion and reconcile generated OpenAPI with the "
                    "interim client contract. Run real backend checks; integration follows. "
                    if phase == "backend" else
                    f"Implement only the {phase} portion against the API contract and fixtures. "
                    "Whole-product backend verification remains a later-phase obligation. "
                )
                + str(task.get("description", ""))
            )
            dependencies = set().union(*(
                projected_dependencies(item) for item in task.get("dependencies", [])
            ))
            projected["dependencies"] = sorted(dependencies - {task_id})
            ordered.append(projected)

    for task in tasks:
        visit(task["task_id"])
    return ordered
