import json
import re
from pathlib import Path

import pytest

from ai_workflow.cli import main
from ai_workflow.design import classify_design_inputs
from ai_workflow.discovery import detect
from ai_workflow.frameworks import detect_prd_frameworks, resolve_frameworks
from ai_workflow.git import run_git
from ai_workflow.model import PHASES, StateStore
from ai_workflow.pipeline import node_cache_key, ready_phases, validate_control_plane
from ai_workflow.structure import (
    validate_backend_evidence,
    validate_database_evidence,
    validate_structure,
)
from ai_workflow.tokens import parse_token


def test_detects_frameworks() -> None:
    assert detect(["apps/frontend/next.config.ts", "apps/backend/manage.py"]) == {
        "frontend": "nextjs",
        "mobile": "unknown",
        "backend": "django-drf",
        "reasons": ["Django manage.py detected"],
    }


def test_resolves_supported_frameworks_declared_in_prd(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text(
        "# Stack\n\nFrontend framework: Next.js\nBackend framework: Django REST Framework\n"
    )
    assert detect_prd_frameworks(prd) == {"frontend": "nextjs", "backend": "django-drf"}
    assert resolve_frameworks(prd) == {
        "frontend": "nextjs",
        "mobile": "unknown",
        "backend": "django-drf",
    }


def test_resolves_flutter_mobile_declared_in_prd(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text("# Stack\n\nMobile framework: Flutter\nBackend framework: FastAPI\n")
    assert detect_prd_frameworks(prd) == {"mobile": "flutter", "backend": "fastapi"}
    assert resolve_frameworks(prd) == {
        "frontend": "unknown",
        "mobile": "flutter",
        "backend": "fastapi",
    }


def test_rejects_unsupported_prd_framework_declaration(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text("# Stack\n\nFrontend framework: Vue.js\nBackend framework: FastAPI\n")
    with pytest.raises(RuntimeError, match="unsupported frontend framework declaration"):
        resolve_frameworks(prd)


def test_rejects_conflicting_command_and_prd_frameworks(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text("# Stack\n\nFrontend: React\nBackend: FastAPI\n")
    with pytest.raises(RuntimeError, match="frontend framework conflict"):
        resolve_frameworks(prd, frontend="nextjs")


def test_plain_frontend_description_is_not_treated_as_framework_declaration(
    tmp_path: Path,
) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text("# Product\n\nFrontend: responsive customer dashboard\n")
    assert resolve_frameworks(prd) == {
        "frontend": "unknown",
        "mobile": "unknown",
        "backend": "unknown",
    }


def _write_token_image(path: Path) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"token-image")


def test_parses_canonical_token_route_with_multiple_ordered_images(tmp_path: Path) -> None:
    token_dir = tmp_path / "frontend" / "TKN001"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# Login layout\n\n## Description\nFix the layout.\n")
    for name in ("current2.png", "expected2.png", "current1.png", "expected1.png"):
        _write_token_image(token_dir / name)

    token = parse_token(tmp_path, "frontend/TKN001/TOKEN.md")

    assert token["area"] == "frontend"
    assert token["images"] == {
        "current": ["frontend/TKN001/current1.png", "frontend/TKN001/current2.png"],
        "expected": ["frontend/TKN001/expected1.png", "frontend/TKN001/expected2.png"],
    }


def test_rejects_invalid_token_route_and_image_number_gap(tmp_path: Path) -> None:
    wrong = tmp_path / "tokens" / "TKN001"
    wrong.mkdir(parents=True)
    (wrong / "TOKEN.md").write_text("# Bug\n\n## Description\nFix it.\n")
    with pytest.raises(RuntimeError, match="token path must be frontend"):
        parse_token(tmp_path, "tokens/TKN001/TOKEN.md")

    token_dir = tmp_path / "backend" / "TKN002"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# API bug\n\n## Description\nFix it.\n")
    _write_token_image(token_dir / "current2.png")
    with pytest.raises(RuntimeError, match="consecutively numbered from 1"):
        parse_token(tmp_path, "backend/TKN002/TOKEN.md")


def _initialize_token_repository(project: Path, area: str, branch: str) -> None:
    remote = project.parent / f"{project.name}-remote.git"
    remote.mkdir()
    assert run_git(remote, "init", "--bare")[0] == 0
    assert run_git(project, "init")[0] == 0
    assert run_git(project, "switch", "-c", branch)[0] == 0
    assert run_git(project, "config", "user.name", "Token Test")[0] == 0
    assert run_git(project, "config", "user.email", "token@example.com")[0] == 0
    (project / ".gitignore").write_text(".ai/\n")
    application = project / "apps" / area
    application.mkdir(parents=True)
    (application / ".keep").write_text("base\n")
    assert run_git(project, "add", ".gitignore", f"apps/{area}/.keep")[0] == 0
    assert run_git(project, "commit", "-m", "chore: initialize token test")[0] == 0
    assert run_git(project, "remote", "add", "origin", str(remote))[0] == 0
    assert run_git(project, "push", "--set-upstream", "origin", branch)[0] == 0


@pytest.mark.parametrize(
    ("area", "framework", "changed_path", "base_branch"),
    [
        ("frontend", "react", "apps/frontend/fix.tsx", "dolan001"),
        ("mobile", "flutter", "apps/mobile/lib/fix.dart", "dolan-mobile"),
        ("backend", "fastapi", "apps/backend/fix.py", "dolan002"),
        ("frontend", "nextjs", "apps/frontend/fix.tsx", "main"),
    ],
)
def test_resolve_token_verifies_and_reuses_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    area: str,
    framework: str,
    changed_path: str,
    base_branch: str,
) -> None:
    StateStore(tmp_path).create(
        project_id="token-test",
        mode="new",
        frontend=framework if area == "frontend" else "react",
        backend=framework if area == "backend" else "fastapi",
        baseline=None,
        branch=None,
        assumptions=[],
        mobile=framework if area == "mobile" else "unknown",
    )
    _initialize_token_repository(tmp_path, area, base_branch)
    token_dir = tmp_path / area / "TKN001"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# Scoped fix\n\n## Description\nResolve it.\n")
    calls: list[str] = []
    pull_request_arguments: list[str] = []

    def fake_token_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter
        assert "build-context-bundle/SKILL.md" in prompt
        assert "recover-failure/SKILL.md" not in prompt
        bundle_match = re.search(r"Bounded context bundle: (.+)", prompt)
        assert bundle_match
        bundle = json.loads(Path(bundle_match.group(1)).read_text())
        assert len(bundle["selected_files"]) <= 12
        assert bundle["selected_characters"] <= 60000
        selected = {item["path"] for item in bundle["selected_files"]}
        assert f"{area}/TKN001/TOKEN.md" in selected
        assert bundle["prior_failure"] is None
        if "Required plan:" in prompt:
            calls.append("diagnosis")
            plan_match = re.search(r"Required plan: (.+)", prompt)
            assert plan_match
            Path(plan_match.group(1)).write_text(
                json.dumps(
                    {
                        "summary": "Resolve scoped token",
                        "diagnosis": "The scoped implementation is incomplete.",
                        "steps": ["Apply the scoped correction."],
                        "files": [changed_path],
                        "checks": ["Run the focused test."],
                        "risks": [],
                    }
                )
            )
            return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}
        calls.append("implementation")
        assert ".ai/token-runs/TKN001/plan.json" in selected
        changed = project / changed_path
        changed.parent.mkdir(parents=True, exist_ok=True)
        changed.write_text("resolved\n")
        evidence_match = re.search(r"Required evidence: (.+)", prompt)
        assert evidence_match
        Path(evidence_match.group(1)).write_text(
            json.dumps(
                {
                    "verified": True,
                    "summary": "Resolved scoped token",
                    "changed_paths": [changed_path],
                    "checks": [{"name": "focused", "passed": True}],
                    "scope_expansions": [],
                }
            )
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    def fake_gh(project: Path, *arguments: str) -> tuple[int, str]:
        del project
        if arguments[:2] == ("pr", "view"):
            return 1, "not found"
        pull_request_arguments.extend(arguments)
        return 0, "https://github.com/example/project/pull/1"

    monkeypatch.setattr("ai_workflow.tokens._run_adapter", fake_token_agent)
    monkeypatch.setattr("ai_workflow.tokens._run_gh", fake_gh)
    arguments = [
        "resolve-token",
        "--project",
        str(tmp_path),
        "--token",
        f"{area}/TKN001/TOKEN.md",
    ]
    assert main(arguments) == 0
    waiting = json.loads((tmp_path / ".ai" / "token-runs" / "TKN001" / "state.json").read_text())
    assert waiting["status"] == "awaiting_approval"
    assert waiting["base_branch"] == base_branch
    assert run_git(tmp_path, "branch", "--show-current")[1] == base_branch
    assert main([*arguments, "--approve", "--github-user", "test-user"]) == 0
    assert main(arguments) == 0
    assert calls == ["diagnosis", "implementation"]
    token_state = json.loads(
        (tmp_path / ".ai" / "token-runs" / "TKN001" / "state.json").read_text()
    )
    assert token_state["status"] == "pr_created"
    assert token_state["base_branch"] == base_branch
    assert token_state["source_branch"] == "ai/test-user/tkn001"
    assert pull_request_arguments[pull_request_arguments.index("--base") + 1] == base_branch
    assert (
        pull_request_arguments[pull_request_arguments.index("--head") + 1] == "ai/test-user/tkn001"
    )


def test_resolve_token_blocks_changes_outside_area_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    StateStore(tmp_path).create(
        project_id="token-test",
        mode="new",
        frontend="react",
        backend="fastapi",
        baseline=None,
        branch=None,
        assumptions=[],
    )
    _initialize_token_repository(tmp_path, "frontend", "dolan003")
    token_dir = tmp_path / "frontend" / "TKN003"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# UI fix\n\n## Description\nResolve it.\n")
    implementation_attempts = 0

    def unsafe_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal implementation_attempts
        del adapter
        assert "build-context-bundle/SKILL.md" in prompt
        bundle_match = re.search(r"Bounded context bundle: (.+)", prompt)
        assert bundle_match
        bundle = json.loads(Path(bundle_match.group(1)).read_text())
        assert len(bundle["selected_files"]) <= 12
        assert bundle["selected_characters"] <= 60000
        if "Required plan:" in prompt:
            assert "recover-failure/SKILL.md" not in prompt
            assert bundle["prior_failure"] is None
            plan_match = re.search(r"Required plan: (.+)", prompt)
            assert plan_match
            Path(plan_match.group(1)).write_text(
                json.dumps(
                    {
                        "summary": "Resolve UI token",
                        "diagnosis": "The UI implementation is incomplete.",
                        "steps": ["Correct the frontend."],
                        "files": ["apps/frontend/fix.tsx"],
                        "checks": ["Run frontend tests."],
                        "risks": [],
                    }
                )
            )
            return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}
        implementation_attempts += 1
        if implementation_attempts == 1:
            assert "recover-failure/SKILL.md" not in prompt
            assert bundle["prior_failure"] is None
        else:
            assert "recover-failure/SKILL.md" in prompt
            assert "outside frontend scope" in bundle["prior_failure"]
        changed = project / "apps" / "backend" / "unsafe.py"
        changed.parent.mkdir(parents=True, exist_ok=True)
        changed.write_text("unsafe\n")
        evidence_match = re.search(r"Required evidence: (.+)", prompt)
        assert evidence_match
        Path(evidence_match.group(1)).write_text(
            json.dumps(
                {
                    "verified": True,
                    "summary": "unsafe",
                    "changed_paths": ["apps/backend/unsafe.py"],
                    "checks": [{"name": "focused", "passed": True}],
                    "scope_expansions": [],
                }
            )
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.tokens._run_adapter", unsafe_agent)
    monkeypatch.setattr(
        "ai_workflow.tokens._run_gh",
        lambda project, *arguments: (0, "https://github.com/example/project/pull/3"),
    )
    diagnose = [
        "resolve-token",
        "--project",
        str(tmp_path),
        "--token",
        "frontend/TKN003/TOKEN.md",
    ]
    assert main(diagnose) == 0
    assert main([*diagnose, "--approve", "--github-user", "test-user"]) == 1
    token_state = json.loads(
        (tmp_path / ".ai" / "token-runs" / "TKN003" / "state.json").read_text()
    )
    assert token_state["status"] == "blocked"
    assert token_state["attempts"] == 3
    assert main([*diagnose, "--approve", "--github-user", "test-user"]) == 1
    resumed_state = json.loads(
        (tmp_path / ".ai" / "token-runs" / "TKN003" / "state.json").read_text()
    )
    assert resumed_state["unverified_changed_paths"] == ["apps/backend/unsafe.py"]


def test_init_inspect_reconcile_plan(tmp_path: Path, capsys: object) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRD.md").write_text("# Authentication\n\n- AUTH-001 User can register.\n")
    assert (
        main(
            [
                "init",
                "--project",
                str(tmp_path),
                "--prd",
                "docs/PRD.md",
                "--frontend",
                "nextjs",
                "--backend",
                "django-drf",
            ]
        )
        == 0
    )
    assert main(["inspect", "--project", str(tmp_path), "--deep"]) == 0
    assert main(["reconcile", "--project", str(tmp_path)]) == 0
    assert main(["plan", "--project", str(tmp_path), "--remaining"]) == 0
    queue = json.loads((tmp_path / ".ai" / "task-queue.json").read_text())
    assert queue["tasks"][0]["requirement_ids"] == ["AUTH-001"]
    assert not (tmp_path / "apps").exists()


def test_clean_state_requires_confirmation(tmp_path: Path) -> None:
    (tmp_path / ".ai").mkdir()
    assert main(["clean-state", "--project", str(tmp_path)]) == 1
    assert (tmp_path / ".ai").exists()


def test_control_plane_is_fully_connected() -> None:
    report = validate_control_plane()
    assert report["valid"] is True
    assert report["phases"] == 9
    assert report["nodes"] == 31
    assert report["agentic_nodes"] == 20
    assert report["execution_groups"][3:6] == [["frontend"], ["mobile"], ["backend"]]


def test_scheduler_unlocks_only_the_next_sequential_phase() -> None:
    assert ready_phases(set(), set()) == ["bootstrap"]
    assert ready_phases({"bootstrap"}, set()) == ["requirements"]
    completed = {"bootstrap", "requirements", "design"}
    assert ready_phases(completed, set()) == ["frontend"]
    assert ready_phases(completed | {"frontend"}, set()) == ["mobile"]
    assert ready_phases(completed | {"frontend", "mobile"}, set()) == ["backend"]


def test_cache_key_changes_only_when_declared_inputs_change(tmp_path: Path) -> None:
    source = tmp_path / "requirements.json"
    source.write_text("one")
    first = node_cache_key(tmp_path, "requirements/plan", ["requirements.json"])
    (tmp_path / "unrelated.txt").write_text("ignored")
    assert node_cache_key(tmp_path, "requirements/plan", ["requirements.json"]) == first
    source.write_text("two")
    assert node_cache_key(tmp_path, "requirements/plan", ["requirements.json"]) != first


def test_one_shot_dry_run_creates_safe_branch_without_application_code(
    tmp_path: Path, capsys: object
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    assert (
        main(
            [
                "one-shot",
                "--project",
                str(tmp_path),
                "--prd",
                "docs/PRD.md",
                "--frontend",
                "react",
                "--backend",
                "fastapi",
                "--github-user",
                "Test User",
                "--branch-feature",
                "Account Build",
            ]
        )
        == 0
    )
    code, branch = run_git(tmp_path, "branch", "--show-current")
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert code == 0 and branch == "ai/test-user/account-build"
    assert state["completed_phases"] == ["bootstrap"]
    assert not (tmp_path / "apps").exists()


@pytest.mark.parametrize(
    ("files", "mode", "action"),
    [
        (
            {"page.html": "<!doctype html><title>Account</title>"},
            "html_supplied",
            "validate_and_approve_supplied_html",
        ),
        (
            {"page.png": b"\x89PNG\r\n\x1a\n"},
            "screenshot_supplied",
            "generate_html_from_visual_evidence_and_prd",
        ),
        ({}, "prd_only", "generate_html_from_prd"),
        (
            {
                "page.html": "<!doctype html><title>Account</title>",
                "page.png": b"\x89PNG\r\n\x1a\n",
            },
            "html_supplied",
            "validate_and_approve_supplied_html",
        ),
    ],
)
def test_design_input_routing_is_deterministic(
    tmp_path: Path, files: dict[str, str | bytes], mode: str, action: str
) -> None:
    source = tmp_path / "HTML" / "source"
    source.mkdir(parents=True)
    for name, content in files.items():
        path = source / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
    report = classify_design_inputs(tmp_path)
    assert report["mode"] == mode
    assert report["required_action"] == action
    assert json.loads((tmp_path / ".ai" / "design-inputs.json").read_text())["mode"] == mode


def _fake_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
    del adapter
    phase, node = re.search(r"Phase/node: ([a-z-]+)/([a-z-]+)", prompt).groups()  # type: ignore[union-attr]
    output = re.search(r"Required output: (.+)", prompt).group(1)  # type: ignore[union-attr]
    output = output.replace("{feature_id}", "acc-001")
    path = project / output
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"phase": phase, "node": node}
    if node.startswith("verify-") or "verification" in node or node == "security-review":
        payload["verified"] = True
    if node == "security-review":
        payload["unresolved_critical"] = False
    if output == ".ai/task-queue.json":
        pass
    elif output.endswith(".json"):
        path.write_text(json.dumps(payload))
    else:
        path.write_text(f"# {phase} {node}\n")

    if phase == "design" and node == "establish-html-baseline":
        approved = project / "HTML" / "approved" / "index.html"
        approved.parent.mkdir(parents=True, exist_ok=True)
        approved.write_text("<!doctype html><title>Approved account</title>")
    if phase in {"frontend", "mobile"} and node == "scaffold-target-monorepo":
        contract_path = Path(__file__).resolve().parents[1] / "config" / "target-monorepo.json"
        contract = json.loads(contract_path.read_text())
        for relative in contract["required_files"]:
            root_file = project / relative
            root_file.parent.mkdir(parents=True, exist_ok=True)
            root_file.write_text(f"pilot root artifact: {relative}\n")
        for relative in contract["required_directories"]:
            (project / relative).mkdir(parents=True, exist_ok=True)
    if phase in {"frontend", "mobile"} and node in {
        "implement-frontend-slices",
        "implement-mobile-slices",
    }:
        _create_pack_structure(project, prompt)
        commands = {
            group: [{"argv": ["true"], "cwd": "."}]
            for group in (
                "frontend",
                "mobile",
                "backend",
                "generate-client",
                "contract",
                "integration",
                "e2e",
            )
        }
        manifest = project / ".ai" / "test-commands.json"
        manifest.write_text(json.dumps({"version": 1, "commands": commands}))
    if phase == "backend" and node == "implement-backend-slices":
        _create_pack_structure(project, prompt)
    if phase == "backend" and node == "verify-backend":
        _write_database_evidence(project, prompt)
        _write_backend_evidence(project, prompt)
    if phase == "integration" and node == "connect-feature-slices":
        client = project / "packages" / "api-client" / "index.ts"
        client.parent.mkdir(parents=True, exist_ok=True)
        client.write_text("export type ApiClient = unknown\n")
    return {"returncode": 0, "stdout_tail": "pilot agent complete", "stderr_tail": ""}


def _create_pack_structure(project: Path, prompt: str) -> None:
    pack_text = re.search(r"Selected framework pack: (.+)", prompt).group(1)  # type: ignore[union-attr]
    contract = json.loads((Path(pack_text) / "rules" / "project-structure.json").read_text())
    target = project / contract["target_root"]
    directories = set(contract.get("required_directories", []))
    for relative in contract["required_paths"]:
        path = target / relative
        if relative in directories:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"pilot {contract['framework']} artifact\n")
    path_sets = contract.get("required_path_sets", [])
    for path_set in path_sets:
        for relative in path_set["alternatives"][0]:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"pilot {contract['framework']} locked dependency artifact\n")
    pattern = contract.get("domain_path_pattern")
    if isinstance(pattern, str) and contract.get("minimum_domain_instances", 0) > 0:
        domain = target / pattern.replace("<domain>", "sample")
        domain_directories = set(contract.get("required_domain_directories", []))
        for relative in contract.get("required_domain_paths", []):
            path = domain / relative
            if relative in domain_directories:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"pilot {contract['framework']} domain artifact\n")


def _write_database_evidence(project: Path, prompt: str) -> None:
    pack_text = re.search(r"Selected framework pack: (.+)", prompt).group(1)  # type: ignore[union-attr]
    contract = json.loads((Path(pack_text) / "rules" / "project-structure.json").read_text())
    check_names = (
        "connection",
        "migrate-empty",
        "migration-head",
        "migration-drift",
        "migrate-second",
        "schema",
        "queries",
    )
    evidence = {
        "version": 1,
        "framework": contract["framework"],
        "database": "postgresql",
        "connection": {"passed": True, "server_version": "pilot", "readiness_passed": True},
        "migrations": {
            "passed": True,
            "empty_database_upgrade": True,
            "at_head": True,
            "drift_free": True,
            "second_upgrade_noop": True,
        },
        "schema": {
            "passed": True,
            "tables": ["sample"],
            "constraints_checked": True,
            "indexes_checked": True,
        },
        "queries": {"passed": True, "reviewed_hot_paths": 1, "query_budget_tests": True},
        "checks": [
            {"name": name, "argv": ["true"], "cwd": "apps/backend", "exit_code": 0}
            for name in check_names
        ],
        "verified": True,
    }
    path = project / ".ai" / "evidence" / "database-verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence))


def _write_backend_evidence(project: Path, prompt: str) -> None:
    pack_text = re.search(r"Selected framework pack: (.+)", prompt).group(1)  # type: ignore[union-attr]
    contract = json.loads((Path(pack_text) / "rules" / "project-structure.json").read_text())
    check_names = (
        "import",
        "startup",
        "api",
        "authorization",
        "transactions",
        "openapi",
        "security",
    )
    evidence = {
        "version": 1,
        "framework": contract["framework"],
        "runtime": {
            "import_passed": True,
            "startup_passed": True,
            "readiness_passed": True,
        },
        "api": {
            "contract_passed": True,
            "success_and_negative_passed": True,
            "authorization_passed": True,
        },
        "transactions": {"passed": True, "concurrency_cases": 1},
        "openapi": {"passed": True},
        "security": {"passed": True},
        "checks": [
            {"name": name, "argv": ["true"], "cwd": "apps/backend", "exit_code": 0}
            for name in check_names
        ],
        "verified": True,
    }
    path = project / ".ai" / "evidence" / "backend-verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence))


@pytest.mark.parametrize(
    ("input_flag", "filename", "content", "expected_mode", "frontend", "backend"),
    [
        (
            "--html",
            "supplied.html",
            "<!doctype html><title>Supplied</title>",
            "html_supplied",
            "nextjs",
            "django-drf",
        ),
        (
            "--screenshot",
            "screen.png",
            b"\x89PNG\r\n\x1a\n",
            "screenshot_supplied",
            "react",
            "fastapi",
        ),
        (None, None, None, "prd_only", "nextjs", "fastapi"),
    ],
)
def test_complete_one_shot_pilot_for_each_design_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    input_flag: str | None,
    filename: str | None,
    content: str | bytes | None,
    expected_mode: str,
    frontend: str,
    backend: str,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    arguments = [
        "one-shot",
        "--project",
        str(tmp_path),
        "--prd",
        "docs/PRD.md",
        "--frontend",
        frontend,
        "--backend",
        backend,
        "--github-user",
        "test-user",
        "--branch-feature",
        "pilot",
        "--execute",
    ]
    if input_flag and filename and content is not None:
        supplied = tmp_path / filename
        supplied.write_bytes(content) if isinstance(content, bytes) else supplied.write_text(
            content
        )
        arguments.extend([input_flag, filename])
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    assert main(arguments) == 0
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    design = json.loads((tmp_path / ".ai" / "design-inputs.json").read_text())
    assert state["status"] == "complete"
    assert state["completed_phases"] == list(PHASES)
    assert design["mode"] == expected_mode
    assert (tmp_path / "HTML" / "approved" / "index.html").is_file()
    frontend_entry = "app/page.tsx" if frontend == "nextjs" else "src/main.tsx"
    backend_entry = "manage.py" if backend == "django-drf" else "app/main.py"
    assert (tmp_path / "apps" / "frontend" / frontend_entry).is_file()
    assert (tmp_path / "apps" / "backend" / backend_entry).is_file()
    assert (tmp_path / "packages" / "api-client" / "index.ts").is_file()


def test_stage_commands_stop_at_design_and_html_without_creating_monorepo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)

    arguments = [
        "start-design",
        "--project",
        str(tmp_path),
        "--github-user",
        "test-user",
        "--adapter",
        "codex",
    ]
    assert main(arguments) == 0
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["completed_phases"] == ["bootstrap", "requirements"]
    assert (tmp_path / "HTML" / "design-specification.md").is_file()
    assert not (tmp_path / "HTML" / "approved" / "index.html").exists()
    assert not (tmp_path / "apps").exists()
    assert not (tmp_path / "README.md").exists()

    assert main(["start-generatehtml", "--project", str(tmp_path), "--adapter", "codex"]) == 0
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["completed_phases"] == ["bootstrap", "requirements", "design"]
    assert (tmp_path / "HTML" / "approved" / "index.html").is_file()
    assert not (tmp_path / "apps").exists()
    assert not (tmp_path / "README.md").exists()


def test_codex_skills_are_directly_discoverable_from_agents_submodule() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "skills" / "catalog.json").read_text())
    for item in catalog["skills"]:
        skill = root / item["path"]
        content = skill.read_text()
        assert "{{WORKFLOW_PATH}}" not in content
        assert ".agents" in content


def test_agent_node_retries_with_failure_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    attempts = 0

    def flaky_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        assert "build-context-bundle/SKILL.md" in prompt
        bundle_match = re.search(r"Bounded context bundle: (.+)", prompt)
        assert bundle_match
        bundle = json.loads(Path(bundle_match.group(1)).read_text())
        assert len(bundle["selected_files"]) <= 12
        assert bundle["selected_characters"] <= 60000
        if attempts == 1:
            assert "recover-failure/SKILL.md" not in prompt
            assert bundle["prior_failure"] is None
            return {"returncode": 1, "stdout_tail": "", "stderr_tail": "temporary failure"}
        if attempts == 2:
            assert "Retry context from the prior failed attempt" in prompt
            assert "recover-failure/SKILL.md" in prompt
            assert "temporary failure" in bundle["prior_failure"]
        return _fake_agent(project, adapter, prompt)

    monkeypatch.setattr("ai_workflow.execution._run_adapter", flaky_agent)
    arguments = [
        "start-design",
        "--project",
        str(tmp_path),
        "--github-user",
        "test-user",
        "--adapter",
        "codex",
    ]
    assert main(arguments) == 0
    failures = (tmp_path / ".ai" / "failures.jsonl").read_text().splitlines()
    record = json.loads(failures[0])
    assert record["status"] == "resolved"
    assert record["attempts"] == 1


def test_resume_build_rejects_a_different_git_branch(tmp_path: Path) -> None:
    (tmp_path / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    arguments = [
        "init",
        "--project",
        str(tmp_path),
        "--prd",
        "PRD.md",
        "--github-user",
        "test-user",
    ]
    assert main(arguments) == 0
    assert run_git(tmp_path, "switch", "-c", "ai/test-user/other-feature")[0] == 0
    assert main(["resume-build", "--project", str(tmp_path)]) == 1


def test_start_build_runs_every_phase_from_auto_discovered_prd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    arguments = [
        "start-build",
        "--project",
        str(tmp_path),
        "--frontend",
        "react",
        "--backend",
        "fastapi",
        "--github-user",
        "test-user",
        "--adapter",
        "codex",
    ]
    assert main(arguments) == 0
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["status"] == "complete"
    assert state["completed_phases"] == list(PHASES)
    assert (tmp_path / "HTML" / "approved" / "index.html").is_file()
    assert (tmp_path / "apps" / "frontend" / "src" / "main.tsx").is_file()
    assert (tmp_path / "apps" / "backend" / "app" / "main.py").is_file()


def test_start_build_uses_frameworks_declared_in_prd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Account\n\n"
        "Frontend framework: Next.js\n"
        "Backend framework: Django REST Framework\n\n"
        "- ACC-001 User can view an account.\n"
    )
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    arguments = [
        "start-build",
        "--project",
        str(tmp_path),
        "--github-user",
        "test-user",
        "--adapter",
        "codex",
    ]
    assert main(arguments) == 0
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["frameworks"] == {
        "frontend": "nextjs",
        "mobile": "unknown",
        "backend": "django-drf",
    }
    assert (tmp_path / "apps" / "frontend" / "app" / "page.tsx").is_file()
    assert (tmp_path / "apps" / "backend" / "manage.py").is_file()


def test_start_build_supports_flutter_only_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Mobile account\n\n"
        "Mobile framework: Flutter\n"
        "Backend framework: FastAPI\n\n"
        "- ACC-001 User can view an account on Android and iOS.\n"
    )
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    assert (
        main(
            [
                "start-build",
                "--project",
                str(tmp_path),
                "--github-user",
                "test-user",
                "--adapter",
                "codex",
            ]
        )
        == 0
    )
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["frameworks"] == {
        "frontend": "unknown",
        "mobile": "flutter",
        "backend": "fastapi",
    }
    assert state["completed_phases"] == list(PHASES)
    assert not (tmp_path / "apps" / "frontend").exists()
    assert (tmp_path / "apps" / "mobile" / "lib" / "main.dart").is_file()
    assert (tmp_path / "apps" / "mobile" / "android").is_dir()
    assert (tmp_path / "apps" / "mobile" / "ios").is_dir()
    assert (tmp_path / "apps" / "backend" / "app" / "main.py").is_file()


def test_start_build_supports_web_and_flutter_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Everywhere account\n\n"
        "Frontend framework: React\n"
        "Mobile framework: Flutter\n"
        "Backend framework: Django REST Framework\n\n"
        "- ACC-001 User can view an account on web, Android, and iOS.\n"
    )
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    assert (
        main(
            [
                "start-build",
                "--project",
                str(tmp_path),
                "--github-user",
                "test-user",
                "--adapter",
                "codex",
            ]
        )
        == 0
    )
    assert (tmp_path / "apps" / "frontend" / "src" / "main.tsx").is_file()
    assert (tmp_path / "apps" / "mobile" / "lib" / "main.dart").is_file()
    assert (tmp_path / "apps" / "backend" / "manage.py").is_file()


def test_start_mobile_stops_without_building_declared_web(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Everywhere account\n\n"
        "Frontend framework: React\n"
        "Mobile framework: Flutter\n"
        "Backend framework: FastAPI\n\n"
        "- ACC-001 User can view an account.\n"
    )
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    assert (
        main(
            [
                "start-mobile",
                "--project",
                str(tmp_path),
                "--github-user",
                "test-user",
                "--adapter",
                "codex",
            ]
        )
        == 0
    )
    state = json.loads((tmp_path / ".ai" / "state.json").read_text())
    assert state["completed_phases"] == ["bootstrap", "requirements", "design", "mobile"]
    assert not (tmp_path / "apps" / "frontend").exists()
    assert (tmp_path / "apps" / "mobile" / "lib" / "main.dart").is_file()
    assert not (tmp_path / "apps" / "backend" / "app" / "main.py").exists()


def test_start_build_requires_only_missing_framework_before_initialization(
    tmp_path: Path, capsys: object
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Account\n\nFrontend framework: React\n\n- ACC-001 User can view an account.\n"
    )
    assert main(["start-build", "--project", str(tmp_path), "--github-user", "test-user"]) == 1
    assert "backend: django-drf or fastapi" in capsys.readouterr().err
    assert not (tmp_path / ".ai").exists()


def test_existing_design_run_requires_a_client_before_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: object
) -> None:
    (tmp_path / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    monkeypatch.setattr("ai_workflow.execution._run_adapter", _fake_agent)
    assert (
        main(
            [
                "start-design",
                "--project",
                str(tmp_path),
                "--github-user",
                "test-user",
            ]
        )
        == 0
    )
    assert main(["start-backend", "--project", str(tmp_path), "--backend", "fastapi"]) == 1
    assert "client: react, nextjs, or flutter" in capsys.readouterr().err


def test_structure_contract_fails_closed_for_missing_paths(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "react_ai"
    with pytest.raises(RuntimeError, match="structure is invalid"):
        validate_structure(tmp_path, pack, "frontend")
    report = json.loads((tmp_path / ".ai" / "evidence" / "structure" / "frontend.json").read_text())
    assert report["valid"] is False
    assert "package.json" in report["missing_paths"]


def test_backend_structure_requires_a_complete_domain(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "fastapi_ai"
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    target = tmp_path / contract["target_root"]
    directories = set(contract["required_directories"])
    for relative in contract["required_paths"]:
        path = target / relative
        if relative in directories:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test artifact\n")
    with pytest.raises(RuntimeError, match="requires at least 1 domain"):
        validate_structure(tmp_path, pack, "backend")


@pytest.mark.parametrize("pack_name", ["drf_ai", "fastapi_ai"])
def test_backend_structure_accepts_minimal_generated_domain(
    tmp_path: Path, pack_name: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)

    report = validate_structure(tmp_path, pack, "backend")

    assert report["valid"] is True
    assert report["missing_path_sets"] == []
    assert report["source_violations"] == []


@pytest.mark.parametrize("pack_name", ["drf_ai", "fastapi_ai"])
def test_backend_structure_accepts_complete_api_capability(
    tmp_path: Path, pack_name: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    domain = tmp_path / contract["target_root"] / contract["domain_path_pattern"].replace(
        "<domain>", "sample"
    )
    api_group = next(
        group
        for group in contract["conditional_domain_groups"]
        if group["name"] in {"rest-api", "json-api"}
    )
    directories = set(api_group["required_directories"])
    for relative in api_group["required_paths"]:
        candidate = domain / relative
        if relative in directories:
            candidate.mkdir(parents=True, exist_ok=True)
        else:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("generated API capability artifact\n")

    report = validate_structure(tmp_path, pack, "backend")

    assert api_group["name"] in report["active_domain_groups"][
        contract["domain_path_pattern"].replace("<domain>", "sample")
    ]
    assert report["valid"] is True


def test_backend_structure_requires_a_resolved_dependency_lock(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "fastapi_ai"
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    selected_lock = contract["required_path_sets"][0]["alternatives"][0][0]
    (tmp_path / contract["target_root"] / selected_lock).unlink()

    with pytest.raises(RuntimeError, match="missing_sets=.*dependency-lock"):
        validate_structure(tmp_path, pack, "backend")


@pytest.mark.parametrize(
    ("pack_name", "trigger", "expected_missing"),
    [
        ("drf_ai", "views.py", "rest-api:serializers/__init__.py"),
        ("fastapi_ai", "routes.py", "json-api:schemas/__init__.py"),
    ],
)
def test_backend_conditional_domain_groups_fail_closed(
    tmp_path: Path, pack_name: str, trigger: str, expected_missing: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    domain = tmp_path / contract["target_root"] / contract["domain_path_pattern"].replace(
        "<domain>", "sample"
    )
    (domain / trigger).write_text("trigger conditional API capability\n")

    with pytest.raises(RuntimeError, match="structure is invalid"):
        validate_structure(tmp_path, pack, "backend")

    report_path = tmp_path / ".ai" / "evidence" / "structure" / "backend.json"
    report = json.loads(report_path.read_text())
    assert any(expected_missing in value for value in report["missing_domain_paths"])


@pytest.mark.parametrize(
    ("pack_name", "relative", "source", "rule"),
    [
        (
            "drf_ai",
            "sample/serializers/input.py",
            "from sample.services import create_order\n",
            "serializers-do-not-import-services",
        ),
        (
            "fastapi_ai",
            "app/domains/sample/routes.py",
            "async def create(db):\n    await db.commit()\n",
            "routes-do-not-persist",
        ),
    ],
)
def test_backend_forbidden_source_rules_fail_closed(
    tmp_path: Path, pack_name: str, relative: str, source: str, rule: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    target = tmp_path / contract["target_root"]
    candidate = target / relative
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(source)

    with pytest.raises(RuntimeError, match="structure is invalid"):
        validate_structure(tmp_path, pack, "backend")

    report_path = tmp_path / ".ai" / "evidence" / "structure" / "backend.json"
    report = json.loads(report_path.read_text())
    assert any(item["rule"] == rule for item in report["source_violations"])


def test_backend_source_rules_ignore_python_comments(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "fastapi_ai"
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    main = tmp_path / contract["target_root"] / "app/main.py"
    main.write_text("# from app.domains.orders import service\n")

    assert validate_structure(tmp_path, pack, "backend")["source_violations"] == []


def test_backend_source_rules_inspect_runtime_configuration_strings(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "fastapi_ai"
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    config = tmp_path / contract["target_root"] / "app/core/config.py"
    config.write_text('DATABASE_URL = "sqlite+aiosqlite:///unsafe.db"\n')

    with pytest.raises(RuntimeError, match="no-sqlite-runtime"):
        validate_structure(tmp_path, pack, "backend")


def test_database_evidence_requires_postgresql_and_complete_checks(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = f"Selected framework pack: {root / 'fastapi_ai'}"
    _write_database_evidence(tmp_path, prompt)
    schema = root / "schemas" / "database-verification.schema.json"
    assert validate_database_evidence(tmp_path, schema, "fastapi")["verified"] is True

    with pytest.raises(RuntimeError, match="does not match the selected backend"):
        validate_database_evidence(tmp_path, schema, "django-drf")

    evidence_path = tmp_path / ".ai" / "evidence" / "database-verification.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["database"] = "sqlite"
    evidence_path.write_text(json.dumps(evidence))
    with pytest.raises(RuntimeError, match="database verification evidence is invalid"):
        validate_database_evidence(tmp_path, schema, "fastapi")


def test_backend_evidence_requires_runtime_api_transaction_and_security_checks(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    prompt = f"Selected framework pack: {root / 'fastapi_ai'}"
    _write_backend_evidence(tmp_path, prompt)
    schema = root / "schemas" / "backend-verification.schema.json"
    assert validate_backend_evidence(tmp_path, schema, "fastapi")["verified"] is True

    with pytest.raises(RuntimeError, match="does not match the selected backend"):
        validate_backend_evidence(tmp_path, schema, "django-drf")

    evidence_path = tmp_path / ".ai" / "evidence" / "backend-verification.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["api"]["authorization_passed"] = False
    evidence_path.write_text(json.dumps(evidence))
    with pytest.raises(RuntimeError, match="backend verification evidence is invalid"):
        validate_backend_evidence(tmp_path, schema, "fastapi")


def test_rejects_a_fake_screenshot(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PRD.md").write_text("# Account\n\n- ACC-001 User can view an account.\n")
    screenshot = tmp_path / "fake.png"
    screenshot.write_bytes(b"not a png")
    assert (
        main(
            [
                "init",
                "--project",
                str(tmp_path),
                "--prd",
                "docs/PRD.md",
                "--screenshot",
                "fake.png",
            ]
        )
        == 1
    )
