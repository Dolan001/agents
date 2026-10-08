import json
from pathlib import Path

import pytest

from ai_workflow.execution import (
    _acquire_path_lease,
    _artifact_ok,
    _backend_compose_project_name,
    _backend_run_lock,
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


def test_backend_foundation_can_create_runnable_framework_structure():
    foundation = task(
        "TASK-FOUNDATION",
        [
            "apps/backend/config/**",
            "apps/backend/accounts/models.py",
            "packages/api-client/**",
            "docs/api/**",
            "tests/contracts/**",
            "compose.yaml",
            "Makefile",
            ".env.example",
        ],
    )
    projected = phase_tasks([foundation], "backend")
    assert projected[0]["allowed_paths"] == [
        "apps/backend/**",
        "apps/backend/config/**",
        "apps/backend/accounts/models.py",
        "packages/api-client/**",
        "docs/api/**",
        "tests/contracts/**",
        "compose.yaml",
        "Makefile",
        ".env.example",
    ]


def test_nonfoundation_backend_slice_gets_shared_integration_paths():
    projected = phase_tasks(
        [task("TASK-ACCOUNTS", ["apps/backend/accounts/**", "compose.yaml"])],
        "backend",
    )
    assert projected[0]["allowed_paths"] == [
        "apps/backend/accounts/**",
        "compose.yaml",
        "apps/backend/core/**",
        "apps/backend/app/main.py",
        "apps/backend/app/api/**",
        "apps/backend/app/core/config.py",
        "apps/backend/pyproject.toml",
        "apps/backend/*.lock",
        "apps/backend/requirements*.txt",
        "docs/api/**",
        "packages/api-client/**",
        "tests/contracts/**",
        ".env.example",
    ]


def test_backend_projection_defers_client_and_later_feature_acceptance():
    realtime = task(
        "TASK-REALTIME",
        ["apps/backend/events/**", "apps/mobile/lib/core/realtime/**"],
    )
    realtime["acceptance_criteria"] = [
        "Persist events; reconnect them from Flutter after message persistence exists."
    ]
    realtime["required_tests"] = ["websocket-auth", "mobile-reconnect"]

    projected = phase_tasks([realtime], "backend")[0]

    assert projected["required_tests"] == ["websocket-auth"]
    assert "mobile-reconnect" in projected["description"]
    assert projected["acceptance_criteria"][0].startswith(
        "Satisfy only backend behavior owned by this feature"
    )


def test_backend_compose_project_name_is_stable_valid_and_checkout_scoped(tmp_path: Path):
    first = tmp_path / "My Backend Project"
    second = tmp_path / "another" / "My Backend Project"
    first.mkdir()
    second.mkdir(parents=True)

    first_name = _backend_compose_project_name(first)

    assert first_name == _backend_compose_project_name(first)
    assert first_name != _backend_compose_project_name(second)
    assert len(first_name) <= 63
    assert first_name.replace("-", "").isalnum()


def test_backend_runtime_rejects_duplicate_workflow(tmp_path: Path):
    with _backend_run_lock(tmp_path):
        with pytest.raises(RuntimeError, match="another backend workflow"):
            with _backend_run_lock(tmp_path):
                pass


def test_backend_runtime_policy_reuses_services_and_scopes_cleanup():
    root = Path(__file__).resolve().parents[1]
    rule = (root / "rules" / "phases" / "backend.md").read_text()
    skill = (root / "skills" / "start-backend" / "SKILL.md").read_text()

    assert "Never run `docker compose up --build` for every feature" in " ".join(rule.split())
    assert "mount source for normal slice checks" in skill
    assert "Retain one current" in skill
    assert "never use an unfiltered or global Docker prune" in skill
    execution = (root / "src" / "ai_workflow" / "execution.py").read_text()
    assert "self-recovering after temporary-" in execution


@pytest.mark.parametrize(
    "relative",
    [
        "drf/skills/implement-drf-vertical-slice/references/database-api-architecture.md",
        "fastapi/skills/implement-fastapi-vertical-slice/references/database-api-architecture.md",
    ],
)
def test_backend_runtime_protocol_avoids_host_database_ports(relative: str):
    content = (Path(__file__).resolve().parents[1] / relative).read_text()
    assert "one uniquely named Compose project" in content
    assert "Do not publish PostgreSQL to host port 5432" in content
    assert "connect to `postgres:5432`" in content
    assert "reuse it until every database" in content


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


@pytest.mark.parametrize("pack", ["drf", "fastapi"])
def test_backend_packs_require_docker_only_runtime_services(pack):
    root = Path(__file__).resolve().parents[1]
    create_name = {
        "drf": "create-django-monorepo-backend",
        "fastapi": "create-fastapi-monorepo-backend",
    }[pack]
    create_skill = (root / pack / "skills" / create_name / "SKILL.md").read_text()
    structure = (root / pack / "rules" / "project-structure.md").read_text()
    database = (
        root
        / pack
        / "skills"
        / f"implement-{pack}-vertical-slice"
        / "references"
        / "database-api-architecture.md"
    ).read_text()

    assert "Docker Compose is the only runtime provider" in create_skill
    assert "Never install or use host Redis or global Celery" in structure
    assert "Docker Compose as the sole PostgreSQL runtime" in database
