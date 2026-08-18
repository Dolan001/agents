import json
import re
import sys
from pathlib import Path

import pytest

from ai_workflow.cli import main
from ai_workflow.commands import run_command_groups
from ai_workflow.deployment import _load_local_aws_environment
from ai_workflow.design import classify_design_inputs
from ai_workflow.design_fidelity import approved_baseline, validate_design_fidelity_evidence
from ai_workflow.discovery import detect
from ai_workflow.frameworks import detect_prd_frameworks, resolve_frameworks
from ai_workflow.git import run_git
from ai_workflow.model import PHASES, StateStore
from ai_workflow.pipeline import node_cache_key, ready_phases, validate_control_plane
from ai_workflow.prd import (
    architecture_decisions,
    sanitize_text,
    validate_decision_sources,
    validate_prd,
)
from ai_workflow.structure import (
    validate_backend_evidence,
    validate_database_evidence,
    validate_realtime_evidence,
    validate_structure,
)
from ai_workflow.tokens import parse_token


def _valid_generated_prd(
    frontend: str = "react",
    backend: str = "fastapi",
    aws: bool = False,
    mobile: bool = False,
) -> str:
    frontend_name = "React" if frontend == "react" else "Next.js"
    backend_name = "FastAPI" if backend == "fastapi" else "Django REST Framework"
    directives = f"Frontend framework: {frontend_name}\nBackend framework: {backend_name}"
    if mobile:
        directives += "\nMobile framework: Flutter"
    if aws:
        directives += "\nDeployment provider: AWS"
    decisions = [
        "Repository layout: Standard application monorepo",
        (
            f"Applications: {frontend_name} web, Flutter mobile, and {backend_name} backend"
            if mobile
            else f"Applications: {frontend_name} web and {backend_name} backend"
        ),
        "Database engine: PostgreSQL",
        "API base path: /api/v1",
        "API contract: OpenAPI with generated typed client",
        "Authentication transport: Secure HTTP-only cookie session with CSRF protection",
        "Authorization model: Customer role with object ownership enforcement",
        "Background jobs: Not required",
        "Scheduled jobs: Not required",
        "Realtime: Not required",
        "File uploads: Not required",
        "Object storage: Not required",
        "External integrations: None",
        "Multi-tenancy: Not required",
        "Audit logging: Required",
        "Localization: Not required",
        (
            "Data retention and deletion: Delete customer data on approved account closure and "
            "retain audit events for 90 days"
        ),
        (
            "Backend delivery: FastAPI domain services"
            if backend == "fastapi"
            else "Backend delivery: Django REST Framework domain services"
        ),
        (
            "Database migrations: Alembic migrations; additive by default"
            if backend == "fastapi"
            else "Database migrations: Django migrations; additive by default"
        ),
        (
            "Backend boundaries: Models, services, repositories, queries, schemas, dependencies, "
            "and routes"
            if backend == "fastapi"
            else (
                "Backend boundaries: Models, services, selectors, serializers, permissions, views, "
                "and URLs"
            )
        ),
        "Query policy: Constraint/index design plus measured query-count or plan budgets",
        (
            "API error contract: Stable validation, authentication, authorization, not-found, "
            "conflict, throttling, and server errors"
        ),
        "Pagination policy: Cursor pagination for account activity",
        "Background execution: Not applicable",
        "Schedule execution: Not applicable",
        "Realtime transport: Not applicable",
    ]
    if backend == "fastapi":
        decisions.append("Database execution model: Async for concurrent API I/O")
    else:
        decisions.append("User model strategy: Custom user model before first migration")
    decisions.extend(
        [
            (
                "Web delivery: React single-page application"
                if frontend == "react"
                else "Web delivery: Next.js App Router application"
            ),
            (
                "Rendering strategy: Browser-rendered routes with explicit route boundaries"
                if frontend == "react"
                else (
                    "Rendering strategy: Server Components by default with minimal Client "
                    "Component boundaries"
                )
            ),
            "Client API boundary: Generated typed client with runtime response validation",
            (
                "Client state coverage: Loading, empty, success, validation, unauthorized, "
                "forbidden, timeout/offline, error, and retry"
            ),
            "Accessibility target: WCAG 2.2 AA",
            "Responsive targets: Mobile, tablet, desktop, zoom, long-content, and overflow",
            "SEO and metadata: Required",
            "Offline behavior: Not required",
        ]
    )
    if frontend == "nextjs":
        decisions.append(
            "Caching strategy: Dynamic account data uses no-store; public help content "
            "revalidates hourly"
        )
    if mobile:
        decisions.extend(
            [
                "Mobile delivery: Flutter application for Android and iOS",
                (
                    "Mobile architecture: Feature-first presentation, application, domain, and "
                    "data boundaries"
                ),
                "Mobile API boundary: Generated typed client with runtime response validation",
                (
                    "Mobile state coverage: Loading, empty, success, validation, unauthorized, "
                    "forbidden, offline, error, and retry"
                ),
                "Mobile offline behavior: Not required",
                "Mobile platform integrations: Secure storage and deep links",
                (
                    "Mobile accessibility target: Screen reader, text scaling, contrast, focus, "
                    "and reduced-motion support"
                ),
                (
                    "Mobile release targets: Android 10 and iOS 16 minimums, release signing "
                    "owned by Mobile, official stores, and staged rollout"
                ),
            ]
        )
    if aws:
        topology = (
            "CloudFront, WAF, ALB, ECS, ECR, RDS PostgreSQL, Route 53, ACM, KMS, "
            "CloudWatch, and AWS Backup"
        )
        if frontend == "react":
            topology += ", with private S3 for static output"
        decisions.extend(
            [
                "AWS region: ap-southeast-1",
                "AWS environment isolation: Separate development, staging, and production accounts",
                "Production domain: app.example.com owned in Route 53",
                "Availability target: 99.9% monthly availability",
                "Recovery point objective: 15 minutes",
                "Recovery time objective: 60 minutes",
                (
                    "Traffic and scaling assumptions: 1000 daily users, 50 requests per second "
                    "peak, and 20% annual growth"
                ),
                "Monthly cost budget: USD 500 approved maximum",
                "Data residency: Singapore region only",
                "Backup retention: 35 days with quarterly restore tests",
                "Deployment approval owner: Release manager",
                f"AWS runtime topology: {topology}",
                (
                    "AWS identity: GitHub OIDC for CI/CD; IAM roles for workloads; Secrets Manager "
                    "for runtime secrets"
                ),
            ]
        )
    sections = {
        "Document Status": "Status: READY",
        "Build Directives": directives,
        "Architecture and Capability Decisions": "\n".join(
            f"- {decision}" for decision in decisions
        ),
        "Product Summary": "A customer account system for registered customers.",
        "Goals and Non-Goals": "Goal: provide account access.\nNon-goal: public social profiles.",
        "Users, Roles, and Permissions": "Customer: may view only their own account.",
        "User Journeys": "A customer signs in and views their account.",
        "Functional Requirements": "- FR-001: An authenticated customer can view their account.",
        "Acceptance Criteria": (
            "- AC-001 (FR-001): Given an authenticated customer, when the account is requested, "
            "then only that customer's account is returned; invalid and unauthorized requests use "
            "the documented error contract."
        ),
        "Business Rules and Edge Cases": "- BR-001: Account ownership cannot be transferred.",
        "Data Entities and Relationships": "Account belongs to exactly one customer.",
        "APIs and Integrations": (
            "A versioned account API returns typed success and error responses."
        ),
        "Client Experience": "The account view has loading, empty, error, and success states.",
        "Authentication and Authorization": (
            "Session authentication and owner authorization are required."
        ),
        "Background Jobs and Realtime": "Not required.",
        "Security, Privacy, and Compliance": "Protect account data and audit denied access.",
        "Non-Functional Requirements": (
            "- NFR-001: The account API responds within 300 ms at p95 under expected peak traffic."
        ),
        "Observability and Audit": "Record request outcomes without sensitive payloads.",
        "Deployment and Environments": (
            "Promote one immutable digest through staging. Production approval protects compatible "
            "singleton migration execution, health checks, alarms, rollback, backup, and restore."
            if aws
            else "Local, test, staging, and production configuration stay separate."
        ),
        "Credential Inventory": (
            "| Service | Variable | Environments | Secret destination | Owner |\n"
            "|---|---|---|---|---|\n"
            "| Database | DATABASE_URL | Local and runtime | "
            "ignored env file or secret manager | Backend |"
            + (
                "\n| AWS | AWS_ACCESS_KEY_ID | Local deployment | ignored env file | Platform |"
                "\n| AWS | AWS_SECRET_ACCESS_KEY | Local deployment | ignored env file | Platform |"
                "\n| AWS | AWS_REGION | All deployment environments | configuration | Platform |"
                if aws
                else ""
            )
        ),
        "Testing and Release Gates": (
            "API, authorization, integration, browser, and security checks must pass."
        ),
        "Assumptions, Dependencies, and Risks": (
            "Assumption: customers already have verified accounts."
        ),
        "Open Questions": "None.",
        "Traceability": (
            "| Requirement | Acceptance | Interface | Data | Tests |\n"
            "|---|---|---|---|---|\n"
            "| FR-001, NFR-001 | AC-001 | Account view and API | Account | "
            "API, authorization, performance, browser |"
        ),
    }
    body = "\n\n".join(f"## {heading}\n\n{content}" for heading, content in sections.items())
    return f"# Product Requirements Document\n\n{body}\n"


def _generated_decision_sources(prd: str) -> dict[str, str]:
    decisions, errors = architecture_decisions(prd)
    assert errors == []
    return {key: "requirements" for key in decisions}


def test_generate_prd_asks_once_then_resumes_to_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "REQUIREMENTS.md").write_text(
        "Build a customer account system. Ask me for any missing architecture choices.\n"
    )
    calls = 0

    def fake_prd_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal calls
        del project, adapter
        calls += 1
        assessment_match = re.search(r"Required assessment output: (.+)", prompt)
        candidate_match = re.search(r"Required candidate output: (.+)", prompt)
        answers_match = re.search(r"Sanitized durable answers: (.+)", prompt)
        assert assessment_match and candidate_match and answers_match
        assessment = Path(assessment_match.group(1))
        candidate = Path(candidate_match.group(1))
        answers = json.loads(Path(answers_match.group(1)).read_text())
        if not answers:
            assessment.write_text(
                json.dumps(
                    {
                        "status": "needs_input",
                        "questions": [
                            {
                                "id": "Q001",
                                "question": "Which supported frontend and backend should be used?",
                                "reason": "The build workflow requires explicit framework choices.",
                            }
                        ],
                        "assumptions": [],
                        "decision_sources": {},
                    }
                )
            )
        else:
            generated = _valid_generated_prd()
            assessment.write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "questions": [],
                        "assumptions": ["Customers already have verified accounts."],
                        "decision_sources": _generated_decision_sources(generated),
                    }
                )
            )
            candidate.write_text(generated)
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.prd._run_adapter", fake_prd_agent)
    command = [
        "generate-prd",
        "--project",
        str(tmp_path),
        "--requirements",
        "REQUIREMENTS.md",
    ]
    assert main(command) == 2
    state = json.loads((tmp_path / ".ai" / "prd-intake" / "state.json").read_text())
    assert state["status"] == "needs_input"
    assert state["questions"][0]["id"] == "Q001"
    assert not (tmp_path / "PRD.md").exists()

    assert main([*command, "--answer", "Q999=Use another stack"]) == 1
    assert calls == 1
    assert main([*command, "--answer", "Q001=React and FastAPI"]) == 0
    assert calls == 2
    assert validate_prd(tmp_path / "PRD.md") == []
    ready = json.loads((tmp_path / ".ai" / "prd-intake" / "state.json").read_text())
    assert ready["status"] == "ready"


def test_generate_prd_blocks_and_redacts_supplied_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_value = "AKIA" + "A" * 16
    credential_value = "-".join(("real", "secret", "value"))
    (tmp_path / "REQUIREMENTS.md").write_text(
        "Build an account system.\n"
        f"AWS_ACCESS_KEY_ID={access_value}\n"
        f"AWS_SECRET_ACCESS_KEY={credential_value}\n"
    )
    called = False

    def forbidden_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal called
        del project, adapter, prompt
        called = True
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.prd._run_adapter", forbidden_agent)
    assert (
        main(
            [
                "generate-prd",
                "--project",
                str(tmp_path),
                "--requirements",
                "REQUIREMENTS.md",
            ]
        )
        == 2
    )
    assert called is False
    intake_text = "\n".join(
        path.read_text() for path in (tmp_path / ".ai" / "prd-intake").glob("*")
    )
    assert access_value not in intake_text
    assert credential_value not in intake_text
    assert "credentials_blocked" in intake_text


def test_generate_prd_repairs_one_invalid_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "REQUIREMENTS.md").write_text(
        "Build a React account client with a FastAPI backend for registered customers.\n"
    )
    calls = 0

    def repairing_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        nonlocal calls
        del project, adapter
        calls += 1
        assessment = Path(re.search(r"Required assessment output: (.+)", prompt).group(1))  # type: ignore[union-attr]
        candidate = Path(re.search(r"Required candidate output: (.+)", prompt).group(1))  # type: ignore[union-attr]
        generated = _valid_generated_prd()
        assessment.write_text(
            json.dumps(
                {
                    "status": "ready",
                    "questions": [],
                    "assumptions": [],
                    "decision_sources": _generated_decision_sources(generated),
                }
            )
        )
        candidate.write_text("# Invalid draft\n" if calls == 1 else generated)
        if calls == 2:
            assert "Repair these deterministic validation failures" in prompt
            assert "missing exact document title" in prompt
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.prd._run_adapter", repairing_agent)
    assert (
        main(
            [
                "generate-prd",
                "--project",
                str(tmp_path),
                "--requirements",
                "REQUIREMENTS.md",
            ]
        )
        == 0
    )
    assert calls == 2
    assert validate_prd(tmp_path / "PRD.md") == []


def test_prd_intake_allows_obvious_credential_placeholders() -> None:
    text = (
        "AWS_ACCESS_KEY_ID=<your aws access key id>\n"
        "AWS_SECRET_ACCESS_KEY=<your aws secret access key>\n"
        "AWS_SESSION_TOKEN=<optional temporary session token>\n"
    )
    sanitized, findings = sanitize_text(text)
    assert sanitized == text
    assert findings == []


@pytest.mark.parametrize(
    ("frontend", "backend", "aws"),
    [
        ("react", "fastapi", False),
        ("nextjs", "django-drf", False),
        ("react", "django-drf", True),
        ("nextjs", "fastapi", True),
    ],
)
def test_prd_validator_accepts_complete_selected_stack_profiles(
    tmp_path: Path, frontend: str, backend: str, aws: bool
) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd(frontend, backend, aws)
    prd.write_text(content)
    assert validate_prd(prd) == []
    assert validate_decision_sources(
        content, {"decision_sources": _generated_decision_sources(content)}
    ) == []


def test_prd_validator_accepts_flutter_profile(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd("nextjs", "django-drf", mobile=True)
    prd.write_text(content)
    assert validate_prd(prd) == []
    assert validate_decision_sources(
        content, {"decision_sources": _generated_decision_sources(content)}
    ) == []


def test_prd_validator_rejects_old_shallow_profile(tmp_path: Path) -> None:
    content = _valid_generated_prd()
    start = content.index("## Architecture and Capability Decisions")
    end = content.index("## Product Summary")
    prd = tmp_path / "PRD.md"
    prd.write_text(content[:start] + content[end:])
    failures = validate_prd(prd)
    assert "missing heading: ## Architecture and Capability Decisions" in failures
    assert "missing architecture decision: database engine" in failures
    assert "missing architecture decision: background jobs" in failures


def test_prd_validator_rejects_assumed_user_owned_decision() -> None:
    content = _valid_generated_prd()
    sources = _generated_decision_sources(content)
    sources["authentication transport"] = "assumption"
    assert validate_decision_sources(content, {"decision_sources": sources}) == [
        "user-owned architecture decision requires an explicit answer: authentication transport"
    ]


def test_prd_validator_rejects_missing_decision_provenance() -> None:
    content = _valid_generated_prd()
    sources = _generated_decision_sources(content)
    del sources["pagination policy"]
    assert validate_decision_sources(content, {"decision_sources": sources}) == [
        "architecture decision has no source: pagination policy"
    ]


def test_prd_validator_rejects_empty_section_and_unmeasurable_nfr(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd().replace(
        "## Product Summary\n\nA customer account system for registered customers.",
        "## Product Summary\n\n",
    ).replace(
        "The account API responds within 300 ms at p95 under expected peak traffic.",
        "The account API should be fast.",
    )
    prd.write_text(content)
    failures = validate_prd(prd)
    assert "empty required section: ## Product Summary" in failures
    assert "non-functional requirements need a measurable numeric target" in failures


def test_prd_validator_rejects_incomplete_aws_recovery_profile(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd(aws=True).replace(
        "- Recovery point objective: 15 minutes\n", ""
    )
    prd.write_text(content)
    assert "missing architecture decision: recovery point objective" in validate_prd(prd)


def test_prd_validator_requires_durable_background_execution(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd().replace(
        "Background jobs: Not required", "Background jobs: Required"
    )
    prd.write_text(content)
    assert (
        "invalid architecture decision for background execution: Not applicable"
        in validate_prd(prd)
    )


def test_explicit_nextjs_directive_allows_react_ecosystem_context(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    content = _valid_generated_prd("nextjs", "fastapi").replace(
        "A customer account system for registered customers.",
        "A customer account system using the React ecosystem for registered customers.",
    )
    prd.write_text(content)
    assert detect_prd_frameworks(prd)["frontend"] == "nextjs"
    assert validate_prd(prd) == []


def test_local_aws_env_is_loaded_only_when_ignored_and_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_git(tmp_path, "init")[0] == 0
    (tmp_path / ".gitignore").write_text(".env\n")
    access_key = "AKIAEXAMPLELOCAL"
    credential_value = "-".join(("local", "secret", "example"))
    (tmp_path / ".env").write_text(
        f"AWS_ACCESS_KEY_ID={access_key}\n"
        f"AWS_SECRET_ACCESS_KEY={credential_value}\n"
        "AWS_REGION=ap-southeast-1\n"
        "AWS_SESSION_TOKEN=<optional temporary session token>\n"
        "APPLICATION_SECRET=must-not-be-loaded\n"
    )
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
    ):
        monkeypatch.delenv(key, raising=False)

    loaded = _load_local_aws_environment(tmp_path)
    assert loaded == {
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": credential_value,
        "AWS_REGION": "ap-southeast-1",
    }
    assert "APPLICATION_SECRET" not in loaded

    manifest = tmp_path / ".ai" / "test-commands.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "commands": {
                    "deploy-staging": [
                        {
                            "argv": [
                                sys.executable,
                                "-c",
                                "import os; print(os.environ['AWS_ACCESS_KEY_ID']); "
                                "print(os.environ['AWS_SECRET_ACCESS_KEY'])",
                            ],
                            "cwd": ".",
                        }
                    ]
                }
            }
        )
    )
    report = run_command_groups(tmp_path, ["deploy-staging"], environment=loaded)
    output = str(report["results"][0]["stdout_tail"])
    assert access_key not in output
    assert credential_value not in output
    assert output.count("[REDACTED]") == 2


def test_local_aws_env_rejects_incomplete_key_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_git(tmp_path, "init")[0] == 0
    (tmp_path / ".gitignore").write_text(".env\n")
    (tmp_path / ".env").write_text("AWS_ACCESS_KEY_ID=AKIAEXAMPLELOCAL\n")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    with pytest.raises(RuntimeError, match="incomplete AWS access key pair"):
        _load_local_aws_environment(tmp_path)


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
        "deployment": "unknown",
    }


def test_resolves_flutter_mobile_declared_in_prd(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text("# Stack\n\nMobile framework: Flutter\nBackend framework: FastAPI\n")
    assert detect_prd_frameworks(prd) == {"mobile": "flutter", "backend": "fastapi"}
    assert resolve_frameworks(prd) == {
        "frontend": "unknown",
        "mobile": "flutter",
        "backend": "fastapi",
        "deployment": "unknown",
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
        "deployment": "unknown",
    }


def test_detects_only_explicit_aws_deployment_declaration(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    prd.write_text(
        "# Stack\n\nFrontend framework: React\nBackend framework: FastAPI\n"
        "Deployment provider: AWS\n\n- OPS-001 Store files in S3.\n"
    )
    assert resolve_frameworks(prd)["deployment"] == "aws"
    prd.write_text(
        "# Product\n\nFrontend framework: React\nBackend framework: FastAPI\n"
        "\n- OPS-001 Integrate an AWS-compatible object service.\n"
    )
    assert resolve_frameworks(prd)["deployment"] == "unknown"
    prd.write_text(
        "# Stack\n\nFrontend framework: React\nBackend framework: FastAPI\n"
        "Deployment provider: AWS and GCP\n"
    )
    with pytest.raises(RuntimeError, match="unsupported deployment provider"):
        resolve_frameworks(prd)


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
    assert report["phases"] == 10
    assert report["nodes"] == 37
    assert report["agentic_nodes"] == 26
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


def _initialize_design_sync_target(project: Path, frontend: str = "react") -> None:
    StateStore(project).create(
        project_id="design-sync",
        mode="new",
        frontend=frontend,
        backend="fastapi",
        baseline=None,
        branch=None,
        assumptions=[],
    )
    approved = project / "HTML" / "approved" / "index.html"
    approved.parent.mkdir(parents=True)
    approved.write_text("<!doctype html><title>Approved account</title>")
    application = project / "apps" / "frontend"
    application.mkdir(parents=True)
    (application / "existing.tsx").write_text("export const Existing = true\n")


def test_sync_design_repairs_and_independently_verifies_frontend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialize_design_sync_target(tmp_path)
    calls: list[str] = []

    def fake_design_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter
        if prompt.startswith("Compare and repair"):
            calls.append("resolver")
            changed = project / "apps" / "frontend" / "design.css"
            changed.write_text(".account { display: grid; }\n")
            _write_design_fidelity_evidence(
                project,
                prompt,
                "frontend",
                changed_paths=["apps/frontend/design.css"],
            )
        else:
            calls.append("verifier")
            _write_design_fidelity_verification(
                project,
                prompt,
                "frontend",
                changed_paths=["apps/frontend/design.css"],
            )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.execution._run_adapter", fake_design_agent)
    assert main(["sync-design", "--project", str(tmp_path)]) == 0
    assert calls == ["resolver", "verifier"]
    assert validate_design_fidelity_evidence(tmp_path, "frontend", "react")["verified"] is True


def test_sync_design_check_only_reports_drift_without_editing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialize_design_sync_target(tmp_path, "nextjs")
    application_before = (tmp_path / "apps" / "frontend" / "existing.tsx").read_text()

    def fake_comparison(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter
        assert prompt.startswith("Compare and do not repair")
        _write_design_fidelity_evidence(
            project,
            prompt,
            "frontend",
            aligned=False,
            mode="check-only",
        )
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.execution._run_adapter", fake_comparison)
    assert (
        main(["sync-design", "--project", str(tmp_path), "--check-only"])
        == 2
    )
    assert (tmp_path / "apps" / "frontend" / "existing.tsx").read_text() == application_before
    comparison = json.loads(
        (
            tmp_path
            / ".ai"
            / "evidence"
            / "design-fidelity"
            / "frontend"
            / "comparison.json"
        ).read_text()
    )
    assert comparison["aligned"] is False
    assert comparison["findings"][0]["severity"] == "major"


def test_sync_design_rejects_repair_scope_leakage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initialize_design_sync_target(tmp_path)

    def unsafe_design_agent(project: Path, adapter: str, prompt: str) -> dict[str, object]:
        del adapter, prompt
        unsafe = project / "apps" / "backend" / "unsafe.py"
        unsafe.parent.mkdir(parents=True)
        unsafe.write_text("unsafe\n")
        return {"returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr("ai_workflow.execution._run_adapter", unsafe_design_agent)
    assert main(["sync-design", "--project", str(tmp_path)]) == 1


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
    if phase in {"frontend", "mobile"} and node.startswith("sync-"):
        _write_design_fidelity_evidence(project, prompt, phase)
    if phase in {"frontend", "mobile"} and node == f"verify-{phase}":
        _write_design_fidelity_verification(project, prompt, phase)
    if phase == "backend" and node == "implement-backend-slices":
        _create_pack_structure(project, prompt)
    if phase == "backend" and node == "verify-backend":
        _write_database_evidence(project, prompt)
        _write_backend_evidence(project, prompt)
    if phase == "deployment" and node == "generate-deployment-assets":
        _create_pack_structure(project, prompt)
    if phase == "deployment" and node == "verify-deployment-assets":
        checks = [
            {"name": name, "passed": True, "evidence": f"pilot {name}"}
            for name in (
                "format", "validate", "security", "identity", "supply-chain",
                "migration", "rollback", "recovery",
            )
        ]
        path.write_text(
            json.dumps(
                {
                    "provider": "aws",
                    "verified": True,
                    "generation_cloud_mutation": False,
                    "checks": checks,
                    "unresolved_critical": [],
                    "artifact_policy": "build-once-promote-digest",
                    "production_approval": "protected-environment-required",
                    "checked_at": "2026-08-16T00:00:00Z",
                }
            )
        )
    if phase == "integration" and node == "connect-feature-slices":
        client = project / "packages" / "api-client" / "index.ts"
        client.parent.mkdir(parents=True, exist_ok=True)
        client.write_text("export type ApiClient = unknown\n")
    return {"returncode": 0, "stdout_tail": "pilot agent complete", "stderr_tail": ""}


def _prompt_framework(prompt: str) -> str:
    selected = re.search(r"Selected framework pack: (.+)", prompt)
    if selected:
        contract = json.loads(
            (Path(selected.group(1)) / "rules" / "project-structure.json").read_text()
        )
        return str(contract["framework"])
    direct = re.search(r"Target/framework: [a-z]+/([a-z]+)", prompt)
    assert direct
    return direct.group(1)


def _design_cases(project: Path, target: str) -> list[dict[str, object]]:
    configurations = (
        [
            ("MOBILE", "web", "mobile", 390, 844),
            ("TABLET", "web", "tablet", 768, 1024),
            ("DESKTOP", "web", "desktop", 1440, 900),
        ]
        if target == "frontend"
        else [
            ("ANDROID", "android", "small-phone", 360, 800),
            ("IOS", "ios", "large-phone", 430, 932),
        ]
    )
    cases: list[dict[str, object]] = []
    for suffix, platform, name, width, height in configurations:
        directory = project / ".ai" / "evidence" / "design-fidelity" / target / "captures"
        directory.mkdir(parents=True, exist_ok=True)
        rendered = directory / f"{suffix.lower()}-rendered.png"
        difference = directory / f"{suffix.lower()}-diff.png"
        rendered.write_bytes(b"\x89PNG\r\n\x1a\n")
        difference.write_bytes(b"\x89PNG\r\n\x1a\n")
        cases.append(
            {
                "id": f"DF-CASE-{suffix}",
                "route": "/account",
                "state": "success",
                "platform": platform,
                "viewport": {
                    "name": name,
                    "width": width,
                    "height": height,
                    "device_scale_factor": 1,
                },
                "baseline_html": "HTML/approved/index.html",
                "rendered_image": rendered.relative_to(project).as_posix(),
                "diff_image": difference.relative_to(project).as_posix(),
            }
        )
    return cases


def _write_design_fidelity_evidence(
    project: Path,
    prompt: str,
    target: str,
    *,
    changed_paths: list[str] | None = None,
    aligned: bool = True,
    mode: str = "repair",
) -> None:
    framework = _prompt_framework(prompt)
    baseline_hash, baseline_files = approved_baseline(project)
    root = project / ".ai" / "evidence" / "design-fidelity" / target
    root.mkdir(parents=True, exist_ok=True)
    cases = _design_cases(project, target)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "target": target,
                "framework": framework,
                "baseline_sha256": baseline_hash,
                "baseline_files": baseline_files,
                "cases": cases,
                "generated_at": "2026-08-18T00:00:00Z",
            }
        )
    )
    findings = (
        []
        if aligned
        else [
            {
                "id": "DF-001",
                "case_id": cases[0]["id"],
                "severity": "major",
                "category": "layout",
                "expected": "Approved account layout",
                "actual": "Rendered account layout differs",
                "requirement_ids": ["ACC-001"],
                "affected_paths": [f"apps/{target}/design"],
                "evidence": [cases[0]["diff_image"]],
            }
        ]
    )
    (root / "comparison.json").write_text(
        json.dumps(
            {
                "version": 1,
                "target": target,
                "framework": framework,
                "baseline_sha256": baseline_hash,
                "mode": mode,
                "aligned": aligned,
                "findings": findings,
                "accepted_differences": [],
                "changed_paths": changed_paths or [],
                "summary": (
                    "Application design matches approved HTML"
                    if aligned
                    else "Meaningful application design drift was found"
                ),
                "verified": aligned,
                "checked_at": "2026-08-18T00:00:00Z",
            }
        )
    )
    (root / "repair-plan.md").write_text("# Design repair plan\n\nNo repair required.\n")


def _write_design_fidelity_verification(
    project: Path,
    prompt: str,
    target: str,
    *,
    changed_paths: list[str] | None = None,
) -> None:
    framework = _prompt_framework(prompt)
    root = project / ".ai" / "evidence" / "design-fidelity" / target
    manifest = json.loads((root / "manifest.json").read_text())
    check_names = (
        ["render", "visual", "responsive", "accessibility", "focused-tests", "build"]
        if target == "frontend"
        else ["golden", "visual", "responsive", "accessibility", "focused-tests", "analysis"]
    )
    (root / "verification.json").write_text(
        json.dumps(
            {
                "version": 1,
                "target": target,
                "framework": framework,
                "baseline_sha256": manifest["baseline_sha256"],
                "resolver_agent": "design-fidelity-resolver",
                "verifier_agent": f"{framework}-independent-verifier",
                "case_ids": [case["id"] for case in manifest["cases"]],
                "changed_paths": changed_paths or [],
                "checks": [
                    {"name": name, "argv": ["true"], "cwd": f"apps/{target}", "exit_code": 0}
                    for name in check_names
                ],
                "unresolved_findings": [],
                "baseline_changed": False,
                "verified": True,
                "checked_at": "2026-08-18T00:00:00Z",
            }
        )
    )


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
    for relative, values in contract.get("required_text", {}).items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(values) + "\n")
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
        "background_tasks": {"required": False},
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
        "deployment": "unknown",
    }
    assert (tmp_path / "apps" / "frontend" / "app" / "page.tsx").is_file()
    assert (tmp_path / "apps" / "backend" / "manage.py").is_file()


def test_start_build_generates_aws_assets_only_when_explicitly_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Account\n\n"
        "Frontend framework: React\n"
        "Backend framework: FastAPI\n"
        "Deployment provider: AWS\n\n"
        "- ACC-001 User can view an account.\n"
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
    assert state["frameworks"]["deployment"] == "aws"
    assert "deployment" in state["completed_phases"]
    assert (tmp_path / "infra" / "environments" / "production").is_dir()
    assert (tmp_path / ".github" / "workflows" / "deploy-production.yml").is_file()
    readiness = json.loads(
        (tmp_path / ".ai" / "evidence" / "deployment" / "readiness.json").read_text()
    )
    assert readiness["verified"] is True
    assert readiness["generation_cloud_mutation"] is False


def test_live_deployment_commands_are_explicit_and_promote_the_staging_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    branch = "ai/test-user/aws-release"
    _initialize_token_repository(tmp_path, "frontend", branch)
    store = StateStore(tmp_path)
    state = store.create(
        project_id="aws-release",
        mode="new",
        frontend="react",
        backend="fastapi",
        baseline=None,
        branch=branch,
        assumptions=[],
        deployment="aws",
    )
    state["completed_phases"] = list(PHASES[: PHASES.index("deployment") + 1])
    store.save(state)
    evidence_root = tmp_path / ".ai" / "evidence" / "deployment"
    evidence_root.mkdir(parents=True, exist_ok=True)
    readiness_checks = [
        {"name": f"check-{index}", "passed": True, "evidence": "verified"}
        for index in range(8)
    ]
    (evidence_root / "readiness.json").write_text(
        json.dumps(
            {
                "provider": "aws",
                "verified": True,
                "generation_cloud_mutation": False,
                "checks": readiness_checks,
                "unresolved_critical": [],
                "artifact_policy": "build-once-promote-digest",
                "production_approval": "protected-environment-required",
                "checked_at": "2026-08-16T00:00:00Z",
            }
        )
    )
    digest = f"sha256:{'a' * 64}"
    source_commit = run_git(tmp_path, "rev-parse", "HEAD")[1]
    (evidence_root / "release.json").write_text(
        json.dumps(
            {
                "provider": "aws",
                "verified": True,
                "source_commit": source_commit,
                "artifact_digest": digest,
                "sbom": True,
                "provenance": True,
                "scan_passed": True,
                "checked_at": "2026-08-16T00:00:00Z",
            }
        )
    )

    def fake_deploy(project: Path, groups: list[str]) -> dict[str, object]:
        group = groups[0]
        environment = group.removeprefix("deploy-")
        (project / ".ai" / "evidence" / "deployment" / f"{environment}.json").write_text(
            json.dumps(
                {
                    "provider": "aws",
                    "environment": environment,
                    "operation": "deploy",
                    "verified": True,
                    "source_commit": source_commit,
                    "artifact_digest": digest,
                    "deployment_id": f"deployment-{environment}",
                    "account_id": "123456789012",
                    "region": "us-east-1",
                    "checks": [{"name": "smoke", "passed": True}],
                    "checked_at": "2026-08-16T00:00:00Z",
                }
            )
        )
        return {"passed": True}

    monkeypatch.setattr("ai_workflow.deployment.run_command_groups", fake_deploy)
    assert main(["deployment-status", "--project", str(tmp_path)]) == 0
    assert main(["deploy-staging", "--project", str(tmp_path)]) == 0
    assert main(["deploy-staging", "--project", str(tmp_path), "--execute"]) == 0
    assert main(["deploy-production", "--project", str(tmp_path), "--execute"]) == 1
    assert (
        main(
            [
                "deploy-production",
                "--project",
                str(tmp_path),
                "--execute",
                "--approve-production",
            ]
        )
        == 0
    )
    production = json.loads((evidence_root / "production.json").read_text())
    assert production["artifact_digest"] == json.loads(
        (evidence_root / "staging.json").read_text()
    )["artifact_digest"]


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
        "deployment": "unknown",
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


def _activate_complete_background_tasks(
    project: Path, pack: Path
) -> tuple[dict[str, object], Path]:
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    target = project / contract["target_root"]
    domain = target / contract["domain_path_pattern"].replace("<domain>", "sample")
    domain_group = next(
        group
        for group in contract["conditional_domain_groups"]
        if group["name"] == "background-tasks"
    )
    for relative in domain_group["required_paths"]:
        candidate = domain / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("background task capability\n")
    path_group = next(
        group
        for group in contract["conditional_path_groups"]
        if group["name"] == "background-tasks"
    )
    for relative in path_group["required_paths"]:
        candidate = target / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("background task infrastructure\n")
    (target / "pyproject.toml").write_text(
        '[project]\ndependencies = ["celery[redis]>=5"]\n'
    )
    (target / ".env.example").write_text(
        "CELERY_BROKER_URL=redis://redis:6379/0\n"
    )
    (target / "compose.yaml").write_text(
        "services:\n"
        "  redis:\n"
        "    image: redis:7\n"
        "  worker:\n"
        "    build: .\n"
        "    command: celery -A app worker\n"
    )
    if contract["framework"] == "django-drf":
        (target / "core/settings/tasks.py").write_text(
            'CELERY_BROKER_URL = env("CELERY_BROKER_URL")\n'
        )
        (target / "core/celery.py").write_text(
            'from celery import Celery\napp = Celery("core")\napp.autodiscover_tasks()\n'
        )
    else:
        (target / "app/worker/config.py").write_text(
            'CELERY_BROKER_URL = settings.CELERY_BROKER_URL\n'
        )
        (target / "app/worker/celery_app.py").write_text(
            "from celery import Celery\n"
            'app = Celery("worker", include=["app.domains.sample.tasks"])\n'
        )
    return contract, target


@pytest.mark.parametrize("pack_name", ["drf_ai", "fastapi_ai"])
def test_backend_background_task_capability_is_complete_and_fail_closed(
    tmp_path: Path, pack_name: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    domain = tmp_path / contract["target_root"] / contract["domain_path_pattern"].replace(
        "<domain>", "sample"
    )
    (domain / "tasks.py").write_text("task trigger\n")

    with pytest.raises(RuntimeError, match="conditional_missing"):
        validate_structure(tmp_path, pack, "backend")

    _activate_complete_background_tasks(tmp_path, pack)
    report = validate_structure(tmp_path, pack, "backend")

    assert report["active_path_groups"] == ["background-tasks"]
    assert report["missing_source_patterns"] == []
    assert "background-tasks" in next(iter(report["active_domain_groups"].values()))


def test_backend_background_task_capability_requires_redis_dependency(
    tmp_path: Path,
) -> None:
    pack = Path(__file__).resolve().parents[1] / "fastapi_ai"
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    _, target = _activate_complete_background_tasks(tmp_path, pack)
    (target / "pyproject.toml").write_text('[project]\ndependencies = ["celery>=5"]\n')

    with pytest.raises(RuntimeError, match="celery-redis-dependency"):
        validate_structure(tmp_path, pack, "backend")


def _activate_complete_backend_realtime(project: Path, pack: Path) -> dict[str, object]:
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    target = project / contract["target_root"]
    domain = target / contract["domain_path_pattern"].replace("<domain>", "sample")
    domain_group = next(
        item for item in contract["conditional_domain_groups"] if item["name"] == "realtime"
    )
    for relative in domain_group["required_paths"]:
        path = domain / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("realtime domain artifact\n")
    path_group = next(
        item for item in contract["conditional_path_groups"] if item["name"] == "realtime"
    )
    for relative in path_group["required_paths"]:
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("realtime infrastructure artifact\n")
    (target / ".env.example").write_text("REALTIME_REDIS_URL=redis://redis:6379/1\n")
    (target / "compose.yaml").write_text(
        "services:\n  redis:\n    image: redis:7\n"
    )
    if contract["framework"] == "django-drf":
        (target / "pyproject.toml").write_text(
            '[project]\ndependencies = ["channels", "channels-redis"]\n'
        )
        (target / "core/settings/realtime.py").write_text(
            'BACKEND = "channels_redis.core.RedisChannelLayer"\n'
        )
        (target / "core/routing.py").write_text("ProtocolTypeRouter({})\n")
        (target / "core/asgi.py").write_text("ProtocolTypeRouter({})\n")
    else:
        (target / "pyproject.toml").write_text(
            '[project]\ndependencies = ["websockets", "redis[hiredis]"]\n'
        )
        (target / "app/realtime/config.py").write_text(
            'REALTIME_REDIS_URL = "redis://redis:6379/1"\n'
        )
    return contract


@pytest.mark.parametrize("pack_name", ["drf_ai", "fastapi_ai"])
def test_backend_realtime_capability_and_evidence_fail_closed(
    tmp_path: Path, pack_name: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    pack = root / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    _activate_complete_backend_realtime(tmp_path, pack)
    structure = validate_structure(tmp_path, pack, "backend")
    schema = root / "schemas" / "realtime-verification.schema.json"

    with pytest.raises(RuntimeError, match="evidence or schema is missing"):
        validate_realtime_evidence(tmp_path, schema, "backend", structure)

    evidence = {
        "version": 1,
        "phase": "backend",
        "transport": "websocket",
        "checks": {
            "authentication": True,
            "authorization": True,
            "protocol_validation": True,
            "payload_and_rate_limits": True,
            "durable_persistence": True,
            "multi_instance": True,
            "redis_recovery": True,
            "slow_consumer": True,
            "graceful_shutdown": True,
        },
        "commands": [
            {"argv": ["pytest", "tests/realtime"], "cwd": "apps/backend", "exit_code": 0}
        ],
        "verified": True,
    }
    path = tmp_path / ".ai/evidence/realtime/backend.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence))

    assert validate_realtime_evidence(tmp_path, schema, "backend", structure) is not None


@pytest.mark.parametrize(
    ("pack_name", "trigger"),
    [
        ("react_ai", "src/realtime/client.ts"),
        ("nextjs_ai", "lib/realtime/client.ts"),
        ("flutter_ai", "lib/core/realtime/realtime_client.dart"),
    ],
)
def test_client_realtime_capability_fails_closed_when_incomplete(
    tmp_path: Path, pack_name: str, trigger: str
) -> None:
    pack = Path(__file__).resolve().parents[1] / pack_name
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    contract = json.loads((pack / "rules" / "project-structure.json").read_text())
    path = tmp_path / contract["target_root"] / trigger
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("WebSocket realtime trigger\n")

    with pytest.raises(RuntimeError, match="conditional_missing"):
        validate_structure(tmp_path, pack, "frontend" if pack_name != "flutter_ai" else "mobile")


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
    _create_pack_structure(tmp_path, prompt)
    validate_structure(tmp_path, root / "fastapi_ai", "backend")
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


def test_backend_evidence_requires_worker_checks_when_background_tasks_are_active(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    pack = root / "fastapi_ai"
    prompt = f"Selected framework pack: {pack}"
    _create_pack_structure(tmp_path, prompt)
    _activate_complete_background_tasks(tmp_path, pack)
    validate_structure(tmp_path, pack, "backend")
    _write_backend_evidence(tmp_path, prompt)
    schema = root / "schemas" / "backend-verification.schema.json"

    with pytest.raises(RuntimeError, match="does not match the generated structure"):
        validate_backend_evidence(tmp_path, schema, "fastapi")

    evidence_path = tmp_path / ".ai" / "evidence" / "backend-verification.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["background_tasks"] = {
        "required": True,
        "broker": "redis",
        "broker_connection_passed": True,
        "worker_startup_passed": True,
        "enqueue_consume_passed": True,
        "retry_passed": True,
        "idempotency_passed": True,
        "duplicate_delivery_passed": True,
        "outbox_passed": True,
        "dead_letter_passed": True,
        "scheduling_required": False,
        "scheduling_passed": None,
    }
    evidence["checks"].extend(
        {"name": name, "argv": ["true"], "cwd": "apps/backend", "exit_code": 0}
        for name in ("broker", "worker", "tasks")
    )
    evidence_path.write_text(json.dumps(evidence))

    assert validate_backend_evidence(tmp_path, schema, "fastapi")["verified"] is True


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
