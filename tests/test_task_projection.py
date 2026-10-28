import json
from pathlib import Path

import pytest

from ai_workflow.execution import (
    _acquire_path_lease,
    _artifact_ok,
    _backend_compose_project_name,
    _backend_contract_repair_request,
    _backend_run_lock,
    _client_foundation_ready,
    _complete_task_contract,
    _leased_test_handoff,
    _release_path_lease,
    _repair_backend_test_matrix,
    _run_backend_contract_repair,
    _run_scoped_dependency_repair,
    _scope_repair_request,
    _scope_repair_requests,
    resume_pending_backend_contract_repair,
)
from ai_workflow.task_projection import phase_tasks


def task(name, paths, dependencies=(), agent="implementer"):
    return {
        "task_id": name, "feature_id": name.lower().removeprefix("task-").removesuffix("-verify"),
        "allowed_paths": paths, "dependencies": list(dependencies), "agent": agent,
    }


def test_blocked_shared_file_gets_exact_separate_repair_scope(tmp_path: Path) -> None:
    shared = "apps/backend/src/example/messages/repository.py"
    source = tmp_path / shared
    source.parent.mkdir(parents=True)
    source.write_text("# existing shared query\n")
    evidence = tmp_path / ".ai/evidence/features/group-messaging/backend.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "verified": False,
                "reviews": [
                    {
                        "type": "dependency_blocker",
                        "status": "blocked",
                        "details": f"Required repair target {shared} is outside the active lease.",
                    }
                ],
            }
        )
    )
    contract = {
        "allowed_paths": ["apps/backend/src/example/messages/group/**"],
        "forbidden_paths": [".agents/**", ".git/**"],
    }
    request = _scope_repair_request(tmp_path, "backend", evidence, contract)
    assert request is not None and request[0] == [shared]

    evidence.write_text(
        json.dumps(
            {
                "verified": False,
                "reviews": [
                    {
                        "type": "scope_repair_request",
                        "status": "blocked",
                        "paths": ["apps/backend/../.agents/AGENTS.md"],
                    }
                ],
            }
        )
    )
    assert _scope_repair_request(tmp_path, "backend", evidence, contract) is None


def test_client_backend_contract_gap_uses_separate_backend_repair_and_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = "apps/backend/src/example/profiles.py"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text("# backend route\n", encoding="utf-8")
    evidence = tmp_path / ".ai/evidence/features/profile/frontend.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({
        "verified": False,
        "reviews": [{
            "type": "scope_repair_request", "status": "blocked", "paths": [relative],
            "details": "Add the authorized profile upload and readback API.",
        }],
    }), encoding="utf-8")
    assert _backend_contract_repair_request(tmp_path, "frontend", evidence)
    assert _backend_contract_repair_request(tmp_path, "backend", evidence) is None

    import ai_workflow.execution as execution

    seen = []
    output = tmp_path / ".ai/evidence/repairs/profile/backend-contract-1.json"
    output.parent.mkdir(parents=True)
    monkeypatch.setattr(execution, "_prompt", lambda *args: (
        "repair backend", {"task_id": "TASK-BACKEND-REPAIR", "allowed_paths": ["apps/backend/**"]}
    ))
    monkeypatch.setattr(execution, "_acquire_path_lease", lambda *args: seen.append("lease"))
    monkeypatch.setattr(execution, "_release_path_lease", lambda *args: seen.append("release"))
    monkeypatch.setattr(execution, "record_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "_artifact_ok", lambda *args: True)

    def adapter(*args):
        seen.append("repair")
        output.write_text(json.dumps({
            "changed_files": [relative], "checks": [{"status": "passed"}],
        }), encoding="utf-8")
        return {"returncode": 0}

    def verify(project, phase, adapter_name, features, **kwargs):
        seen.append("verify")
        assert phase == "backend" and kwargs["verification_only"] is True
        return {"gate": {"passed": True}}

    monkeypatch.setattr(execution, "_run_adapter", adapter)
    monkeypatch.setattr(execution, "execute_phase", verify)
    monkeypatch.setattr(
        "ai_workflow.cli._record_backend_prerequisite_snapshot",
        lambda project: seen.append("snapshot"),
    )
    monkeypatch.setattr(execution, "validate_html_approval", lambda project: None)
    monkeypatch.setattr(
        "ai_workflow.cli._frontend_prerequisite_fingerprint",
        lambda project: {"sha256": "verified"},
    )
    ok, _ = _run_backend_contract_repair(
        tmp_path, "codex-reviewed", {"frameworks": {}},
        ".ai/evidence/features/profile/frontend.json", "frontend", "profile", 1,
    )
    assert ok is True
    assert seen == ["lease", "repair", "release", "verify", "snapshot"]
    snapshot = tmp_path / ".ai/evidence/frontend-prerequisites.json"
    assert json.loads(snapshot.read_text())["sha256"] == "verified"

    evidence.write_text(json.dumps({
        "verified": False,
        "reviews": [{
            "type": "scope_repair_request", "status": "blocked",
            "paths": ["apps/backend/../frontend/src/app.tsx"],
        }],
    }), encoding="utf-8")
    assert _backend_contract_repair_request(tmp_path, "frontend", evidence) is None


@pytest.mark.parametrize("failed_attempts", [1, 3])
def test_backend_contract_repair_retries_distinct_focused_live_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_attempts: int
) -> None:
    import ai_workflow.execution as execution

    runs: list[str] = []
    monkeypatch.setattr(execution, "_prompt", lambda *args: (
        args[-1], {"task_id": f"TASK-{len(runs)}", "allowed_paths": ["apps/backend/**"]}
    ))
    monkeypatch.setattr(execution, "_acquire_path_lease", lambda *args: None)
    monkeypatch.setattr(execution, "_release_path_lease", lambda *args: None)
    monkeypatch.setattr(execution, "record_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "_artifact_ok", lambda *args: True)
    monkeypatch.setattr(
        "ai_workflow.cli._record_backend_prerequisite_snapshot", lambda *args: None
    )

    def adapter(_project: Path, _adapter: str, prompt: str) -> dict:
        runs.append(prompt)
        output = tmp_path / f".ai/evidence/repairs/profile/backend-contract-{len(runs)}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        checks = [{"name": "source", "status": "passed"}]
        if len(runs) <= failed_attempts:
            checks.append(
                {"name": "live", "status": "failed", "reason": f"runtime problem {len(runs)}"}
            )
        output.write_text(
            json.dumps({"changed_files": ["apps/backend/profiles.py"], "checks": checks})
        )
        return {"returncode": 0}

    monkeypatch.setattr(execution, "_run_adapter", adapter)
    monkeypatch.setattr(execution, "execute_phase", lambda *args, **kwargs: (
        runs.append("verify") or {"gate": {"passed": True}}
    ))
    ok, _ = _run_backend_contract_repair(
        tmp_path, "codex-reviewed", {"frameworks": {}},
        ".ai/evidence/features/profile/frontend.json", "mobile", "profile", 1,
    )
    assert ok is True
    assert len(runs) == failed_attempts + 2
    assert "same named object volume" in runs[1]
    assert runs[-1] == "verify"


def test_scoped_diagnostic_hands_test_back_to_owning_slice(tmp_path: Path) -> None:
    relative = "tests/integration/group-messaging/live_check.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text("# live check\n", encoding="utf-8")
    evidence = {
        "reviews": [
            {
                "type": "test_scope_request",
                "status": "blocked",
                "paths": [relative],
            }
        ]
    }
    feature = {
        "allowed_paths": ["tests/integration/group-messaging/**"],
        "forbidden_paths": [".agents/**"],
    }
    assert _leased_test_handoff(tmp_path, evidence, feature) == relative
    feature["allowed_paths"] = ["tests/integration/other-feature/**"]
    assert _leased_test_handoff(tmp_path, evidence, feature) is None


def test_backend_contract_repair_can_fix_client_compose_overlay(tmp_path: Path) -> None:
    state = {"frameworks": {}}
    repair = _complete_task_contract(
        tmp_path,
        "backend/repair-backend-contract/phase",
        "backend",
        [],
        state,
        None,
        required_output=".ai/evidence/repairs/profile/backend-contract-1.json",
        verification="evidence-schema",
    )
    normal = _complete_task_contract(
        tmp_path,
        "backend/implement-backend-slices/phase",
        "backend",
        [],
        state,
        None,
        required_output=".ai/evidence/features/profile/backend.json",
        verification="evidence-schema",
    )
    assert "compose.frontend.yaml" in repair["allowed_paths"]
    assert "compose.frontend.yaml" not in normal["allowed_paths"]


def test_frontend_resume_picks_up_failed_backend_contract_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ai_workflow.execution as execution

    verified = tmp_path / ".ai/evidence/backend-verification.json"
    verified.parent.mkdir(parents=True)
    verified.write_text("{}")
    repair = tmp_path / ".ai/evidence/repairs/profile/backend-contract-1.json"
    repair.parent.mkdir(parents=True)
    repair.write_text(json.dumps({
        "feature_id": "profile", "checks": [{"status": "failed", "name": "live"}],
    }))
    verified.touch()
    import os

    os.utime(verified, ns=(1, 1))
    seen: list[tuple] = []
    monkeypatch.setattr(execution, "_run_backend_contract_repair", lambda *args, **kwargs: (
        seen.append((args, kwargs)) or (True, "recovered")
    ))
    monkeypatch.setattr(execution, "StateStore", lambda _project: type(
        "Store", (), {"load": lambda self: {"frameworks": {}}}
    )())
    assert resume_pending_backend_contract_repair(tmp_path, "codex-reviewed", "frontend") == (
        True, "recovered"
    )
    assert seen[0][0][3] == ".ai/evidence/repairs/profile/backend-contract-1.json"
    assert seen[0][0][6] == 2
    assert seen[0][1]["focused_retry_round"] == 1


def test_independent_shared_repairs_keep_separate_two_file_leases(tmp_path: Path) -> None:
    paths = [
        "apps/backend/src/example/realtime/routes.py",
        "apps/backend/src/example/realtime/service.py",
        "apps/backend/src/example/presence/realtime.py",
    ]
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# existing source\n", encoding="utf-8")
    evidence = tmp_path / "backend.json"
    evidence.write_text(
        json.dumps(
            {
                "verified": False,
                "reviews": [
                    {
                        "type": "scope_repair_request",
                        "status": "blocked",
                        "paths": paths[:2],
                        "details": "wire contract",
                    },
                    {
                        "type": "scope_repair_request",
                        "status": "blocked",
                        "paths": paths[2:],
                        "details": "slow consumer",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    contract = {"allowed_paths": [], "forbidden_paths": [".agents/**"]}
    requests = _scope_repair_requests(tmp_path, "backend", evidence, contract)
    assert [request[0] for request in requests] == [paths[:2], paths[2:]]
    assert requests[0][1] != requests[1][1]


def test_backend_verifier_can_delegate_an_owned_test_file(tmp_path: Path) -> None:
    relative = "apps/backend/tests/messages/test_replay.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text("# typed replay assertion\n", encoding="utf-8")
    evidence = tmp_path / "backend-verification.json"
    evidence.write_text(
        json.dumps(
            {
                "verified": False,
                "reviews": [
                    {
                        "type": "scope_repair_request",
                        "status": "blocked",
                        "paths": [relative],
                        "details": "mypy nested envelope failure",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    contract = {"allowed_paths": ["apps/backend/**"], "forbidden_paths": [".agents/**"]}
    assert _scope_repair_requests(tmp_path, "backend", evidence, contract) == []
    requests = _scope_repair_requests(
        tmp_path, "backend", evidence, contract, allow_owned_paths=True
    )
    assert len(requests) == 1 and requests[0][0] == [relative]


def test_failed_backend_matrix_repairs_and_reruns_within_same_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "artifacts/tests/command-results.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "passed": False,
                "results": [
                    {
                        "returncode": 1,
                        "stdout_tail": "FAILED tests/realtime/test_protocol.py::test_v1_frame",
                        "stderr_tail": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []
    monkeypatch.setattr(
        "ai_workflow.execution._prompt",
        lambda *args: ("repair prompt", {"task_id": "TASK-MATRIX-REPAIR"}),
    )
    monkeypatch.setattr("ai_workflow.execution._acquire_path_lease", lambda *args: None)
    monkeypatch.setattr("ai_workflow.execution._release_path_lease", lambda *args: None)
    monkeypatch.setattr("ai_workflow.execution.record_attempt", lambda *args, **kwargs: None)
    monkeypatch.setattr("ai_workflow.execution._artifact_ok", lambda *args: True)

    def repair_agent(*args: object) -> dict[str, object]:
        calls.append("repair")
        output = tmp_path / ".ai/evidence/backend-test-matrix-repair-1.json"
        output.parent.mkdir(parents=True)
        output.write_text(
            json.dumps(
                {
                    "changed_files": ["apps/backend/tests/realtime/test_protocol.py"],
                    "checks": [{"name": "focused", "status": "passed"}],
                }
            ),
            encoding="utf-8",
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    def rerun(*args: object) -> None:
        calls.append("matrix")
        report.write_text('{"passed": true, "results": []}', encoding="utf-8")

    monkeypatch.setattr("ai_workflow.execution._run_adapter", repair_agent)
    monkeypatch.setattr("ai_workflow.execution._run_deterministic", rerun)
    _repair_backend_test_matrix(tmp_path, "codex", {})
    assert calls == ["repair", "matrix"]


def test_shared_dependency_repair_uses_its_own_lease_and_focused_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = "apps/backend/src/example/messages/repository.py"
    source = tmp_path / shared
    source.parent.mkdir(parents=True)
    source.write_text("# failing query\n")
    failed = ".ai/evidence/features/group-messaging/backend.json"
    failed_path = tmp_path / failed
    failed_path.parent.mkdir(parents=True)
    failed_path.write_text("{}")

    def repair_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter
        output_line = next(
            line.removeprefix("Required output: ")
            for line in prompt.splitlines()
            if line.startswith("Required output: ")
        )
        assert output_line.startswith(
            ".ai/evidence/repairs/group-messaging/backend-shared-dependency-1-"
        )
        leases = json.loads((project / ".ai/path-leases.json").read_text())["leases"]
        assert len(leases) == 1
        assert shared in leases[0]["paths"]
        assert "apps/backend/src/example/messages/group/**" not in leases[0]["paths"]
        source.write_text("# corrected query\n")
        output = project / output_line
        output.parent.mkdir(parents=True)
        output.write_text(
            json.dumps(
                {
                    "feature_id": "group-messaging",
                    "requirement_ids": ["FR-015"],
                    "changed_files": [shared],
                    "checks": [{"name": "focused-postgresql", "status": "passed"}],
                    "reviews": [],
                    "verified": False,
                }
            )
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.execution._run_adapter", repair_agent)
    repaired, reason = _run_scoped_dependency_repair(
        tmp_path,
        "codex",
        "backend",
        {"agent": "selected-backend-agent"},
        {
            "frameworks": {
                "frontend": "unknown",
                "mobile": "unknown",
                "desktop": "unknown",
                "backend": "fastapi",
                "deployment": "unknown",
            },
            "capabilities": {},
        },
        {
            "feature_id": "group-messaging",
            "task_id": "TASK-GROUP-MESSAGING",
            "allowed_paths": ["apps/backend/src/example/messages/group/**"],
            "requirement_ids": ["FR-015"],
        },
        failed,
        [shared],
        1,
    )
    assert repaired and shared in reason
    assert json.loads((tmp_path / ".ai/path-leases.json").read_text())["leases"] == []


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
    assert projected[1]["allowed_paths"] == [
        "apps/frontend/**",
        "apps/frontend/src/app/**",
        "apps/frontend/src/routes/**",
        "apps/frontend/src/services/**",
        "packages/api-client/generate.py",
        "packages/api-client/typescript/**",
        "tests/contracts/**",
    ]
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
    assert "never guess hard-coded lock IDs" in execution
    assert "database-verification.json" in execution
    assert "Both artifacts are required by the backend gate" in execution


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
