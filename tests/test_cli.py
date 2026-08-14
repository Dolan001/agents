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
from ai_workflow.structure import validate_structure
from ai_workflow.tokens import parse_token


def test_detects_frameworks() -> None:
    assert detect(["apps/frontend/next.config.ts", "apps/backend/manage.py"]) == {
        "frontend": "nextjs",
        "backend": "django-drf",
        "reasons": ["Django manage.py detected"],
    }


def test_resolves_supported_frameworks_declared_in_prd(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text(
        "# Stack\n\nFrontend framework: Next.js\nBackend framework: Django REST Framework\n"
    )
    assert detect_prd_frameworks(prd) == {"frontend": "nextjs", "backend": "django-drf"}
    assert resolve_frameworks(prd) == {"frontend": "nextjs", "backend": "django-drf"}


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
    assert resolve_frameworks(prd) == {"frontend": "unknown", "backend": "unknown"}


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


@pytest.mark.parametrize(
    ("area", "framework", "changed_path"),
    [
        ("frontend", "react", "apps/frontend/fix.tsx"),
        ("backend", "fastapi", "apps/backend/fix.py"),
    ],
)
def test_resolve_token_verifies_and_reuses_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    area: str,
    framework: str,
    changed_path: str,
) -> None:
    StateStore(tmp_path).create(
        project_id="token-test",
        mode="new",
        frontend=framework if area == "frontend" else "react",
        backend=framework if area == "backend" else "fastapi",
        baseline=None,
        branch=None,
        assumptions=[],
    )
    (tmp_path / "apps" / area).mkdir(parents=True)
    token_dir = tmp_path / area / "TKN001"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# Scoped fix\n\n## Description\nResolve it.\n")
    calls = 0

    def fake_token_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal calls
        del adapter
        calls += 1
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

    monkeypatch.setattr("ai_workflow.tokens._run_adapter", fake_token_agent)
    arguments = [
        "resolve-token",
        "--project",
        str(tmp_path),
        "--token",
        f"{area}/TKN001/TOKEN.md",
    ]
    assert main(arguments) == 0
    assert main(arguments) == 0
    assert calls == 1
    token_state = json.loads(
        (tmp_path / ".ai" / "token-runs" / "TKN001" / "state.json").read_text()
    )
    assert token_state["status"] == "verified"


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
    (tmp_path / "apps" / "frontend").mkdir(parents=True)
    token_dir = tmp_path / "frontend" / "TKN003"
    token_dir.mkdir(parents=True)
    (token_dir / "TOKEN.md").write_text("# UI fix\n\n## Description\nResolve it.\n")

    def unsafe_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter
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
    assert (
        main(
            [
                "resolve-token",
                "--project",
                str(tmp_path),
                "--token",
                "frontend/TKN003/TOKEN.md",
            ]
        )
        == 1
    )
    token_state = json.loads(
        (tmp_path / ".ai" / "token-runs" / "TKN003" / "state.json").read_text()
    )
    assert token_state["status"] == "blocked"
    assert token_state["attempts"] == 3
    assert (
        main(
            [
                "resolve-token",
                "--project",
                str(tmp_path),
                "--token",
                "frontend/TKN003/TOKEN.md",
            ]
        )
        == 1
    )
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
    assert report["phases"] == 8
    assert report["nodes"] == 27
    assert report["agentic_nodes"] == 17
    assert report["execution_groups"][3:5] == [["frontend"], ["backend"]]


def test_scheduler_unlocks_only_the_next_sequential_phase() -> None:
    assert ready_phases(set(), set()) == ["bootstrap"]
    assert ready_phases({"bootstrap"}, set()) == ["requirements"]
    completed = {"bootstrap", "requirements", "design"}
    assert ready_phases(completed, set()) == ["frontend"]
    assert ready_phases(completed | {"frontend"}, set()) == ["backend"]


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
    if phase == "frontend" and node == "scaffold-target-monorepo":
        contract_path = Path(__file__).resolve().parents[1] / "config" / "target-monorepo.json"
        contract = json.loads(contract_path.read_text())
        for relative in contract["required_files"]:
            root_file = project / relative
            root_file.parent.mkdir(parents=True, exist_ok=True)
            root_file.write_text(f"pilot root artifact: {relative}\n")
        for relative in contract["required_directories"]:
            (project / relative).mkdir(parents=True, exist_ok=True)
    if phase == "frontend" and node == "implement-frontend-slices":
        _create_pack_structure(project, prompt)
        commands = {
            group: [{"argv": ["true"], "cwd": "."}]
            for group in (
                "frontend",
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
        if attempts == 1:
            return {"returncode": 1, "stdout_tail": "", "stderr_tail": "temporary failure"}
        if attempts == 2:
            assert "Retry context from the prior failed attempt" in prompt
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
    assert state["frameworks"] == {"frontend": "nextjs", "backend": "django-drf"}
    assert (tmp_path / "apps" / "frontend" / "app" / "page.tsx").is_file()
    assert (tmp_path / "apps" / "backend" / "manage.py").is_file()


def test_start_build_requires_only_missing_framework_before_initialization(
    tmp_path: Path, capsys: object
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Account\n\nFrontend framework: React\n\n- ACC-001 User can view an account.\n"
    )
    assert main(["start-build", "--project", str(tmp_path), "--github-user", "test-user"]) == 1
    assert "backend: django-drf or fastapi" in capsys.readouterr().err
    assert not (tmp_path / ".ai").exists()


def test_structure_contract_fails_closed_for_missing_paths(tmp_path: Path) -> None:
    pack = Path(__file__).resolve().parents[1] / "react_ai"
    with pytest.raises(RuntimeError, match="structure is invalid"):
        validate_structure(tmp_path, pack, "frontend")
    report = json.loads((tmp_path / ".ai" / "evidence" / "structure" / "frontend.json").read_text())
    assert report["valid"] is False
    assert "package.json" in report["missing_paths"]


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
