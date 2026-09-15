import json
from pathlib import Path

import pytest

from ai_workflow.execution import _artifact_ok, _client_foundation_ready
from ai_workflow.task_projection import phase_tasks


def task(name, paths, dependencies=(), agent="implementer"):
    return {
        "task_id": name, "feature_id": name.lower().removeprefix("task-").removesuffix("-verify"),
        "allowed_paths": paths, "dependencies": list(dependencies), "agent": agent,
    }


def test_client_projection_orders_prerequisites_and_excludes_backend_verifiers():
    tasks = [
        task("TASK-WEB", ["apps/frontend/**"], ["TASK-AUTH-VERIFY"]),
        task("TASK-WEB-VERIFY", [".ai/evidence/web.json"], ["TASK-WEB"], "independent-verifier"),
        task("TASK-AUTH", ["apps/backend/**"], ["TASK-API-VERIFY"]),
        task("TASK-AUTH-VERIFY", [".ai/evidence/auth.json"], ["TASK-AUTH"], "independent-verifier"),
        task("TASK-API-VERIFY", [".ai/evidence/api.json"], ["TASK-API"], "independent-verifier"),
        task("TASK-API", ["packages/api-client/**", "apps/backend/**"]),
    ]
    projected = phase_tasks(tasks, "frontend")
    assert [item["task_id"] for item in projected] == ["TASK-API", "TASK-WEB"]
    assert projected[1]["dependencies"] == ["TASK-API"]
    assert projected[0]["allowed_paths"] == ["packages/api-client/**"]
    assert tasks[0]["dependencies"] == ["TASK-AUTH-VERIFY"]


@pytest.mark.parametrize("dependency", ["TASK-A", "TASK-MISSING"])
def test_bad_dependency_plan_fails_before_dispatch(dependency):
    with pytest.raises(RuntimeError, match="cyclic|unknown"):
        phase_tasks([task("TASK-A", ["apps/frontend/**"], [dependency])], "frontend")


@pytest.mark.parametrize("nested", [False, True])
def test_blocked_evidence_is_not_a_completed_artifact(tmp_path: Path, nested):
    path = tmp_path / "frontend.json"
    blocker = {"status": "BLOCKED", "blockers": [{"code": "MISSING_CLIENT"}]}
    payload = {"reviews": [blocker], "verified": True} if nested else blocker
    path.write_text(json.dumps(payload))
    assert not _artifact_ok(path, "evidence-schema")
    assert not _artifact_ok(path, "verified-true")


def test_readme_only_scaffold_is_not_an_executable_foundation(tmp_path: Path):
    app = tmp_path / "apps/frontend"
    app.mkdir(parents=True)
    (app / "README.md").write_text("Frontend will be created here")
    assert not _client_foundation_ready(
        tmp_path, "frontend", {"checks": [{"status": "passed"}]}
    )
