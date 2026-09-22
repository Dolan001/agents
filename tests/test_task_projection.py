import json
from pathlib import Path

import pytest

from ai_workflow.execution import (
    _acquire_path_lease,
    _artifact_ok,
    _client_foundation_ready,
    _complete_task_contract,
    _release_path_lease,
)
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


def test_frontend_foundation_lease_protects_standalone_compose(tmp_path: Path):
    contract = _complete_task_contract(
        tmp_path, "frontend/prepare-client-foundation/phase", "frontend", [], {}, None,
        required_output=".ai/evidence/frontend-foundation.json",
    )
    assert "compose.frontend.yaml" in contract["allowed_paths"]
    assert "compose.yaml" not in contract["allowed_paths"]
    _acquire_path_lease(tmp_path, contract)
    competing = dict(contract, task_id="TASK-COMPOSE-EDIT", allowed_paths=["compose.frontend.yaml"])
    with pytest.raises(RuntimeError, match="path lease conflicts"):
        _acquire_path_lease(tmp_path, competing)
    _release_path_lease(tmp_path, contract["task_id"])
    _acquire_path_lease(tmp_path, competing)


def test_mobile_foundation_does_not_lease_frontend_compose(tmp_path: Path):
    contract = _complete_task_contract(
        tmp_path, "mobile/prepare-client-foundation/phase", "mobile", [], {}, None,
        required_output=".ai/evidence/mobile-foundation.json",
    )
    assert "compose.frontend.yaml" not in contract["allowed_paths"]
    assert "apps/frontend/**" not in contract["allowed_paths"]
    assert "apps/mobile/**" in contract["allowed_paths"]


def test_design_specification_ignores_downstream_inventory(tmp_path):
    from ai_workflow.execution import _node_input_files
    from ai_workflow.pipeline import node_cache_key

    source = tmp_path / 'HTML/source'
    source.mkdir(parents=True)
    asset = source / 'design.svg'
    asset.write_text('<svg>original</svg>')
    inventory = source / 'inventory.json'
    inventory.write_text('{"specification_hash": "old"}')
    identity = 'design/create-design-specification/phase'

    def key():
        inputs = _node_input_files(tmp_path, 'design', 'create-design-specification')
        return node_cache_key(tmp_path, identity, inputs)

    original = key()
    inventory.write_text('{"specification_hash": "new"}')
    assert key() == original
    asset.write_text('<svg>changed</svg>')
    assert key() != original


@pytest.mark.parametrize('node', [
    'create-design-specification', 'establish-html-baseline', 'verify-html-baseline',
])
def test_design_cache_ignores_only_identical_interim_alias(tmp_path, node):
    from ai_workflow.execution import _node_input_files
    from ai_workflow.pipeline import node_cache_key

    api = tmp_path / 'docs/api'
    api.mkdir(parents=True)
    interim = api / 'openapi.interim.json'
    interim.write_text('{"paths": {}}')

    def key():
        return node_cache_key(tmp_path, node, _node_input_files(tmp_path, 'design', node))

    original = key()
    canonical = api / 'openapi.json'
    canonical.write_bytes(interim.read_bytes())
    assert key() == original
    canonical.write_text('{"paths": {"/new": {}}}')
    assert key() != original
