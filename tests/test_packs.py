import json
from pathlib import Path

import pytest

from ai_workflow.cli import main
from ai_workflow.packs import (
    lightweight_main,
    missing_framework_choices,
    reconcile_selected_packs,
    select_pack_names,
    selected_pack_status,
)


@pytest.mark.parametrize(
    ("frameworks", "capabilities", "deployment", "expected"),
    [
        (
            {"frontend": "react", "mobile": "unknown", "backend": "django-drf"},
            {},
            False,
            {"base", "reactjs", "drf"},
        ),
        (
            {"frontend": "nextjs", "mobile": "unknown", "backend": "fastapi"},
            {},
            False,
            {"base", "nextjs", "fastapi"},
        ),
        (
            {"frontend": "unknown", "mobile": "flutter", "backend": "django-drf"},
            {},
            False,
            {"base", "flutter", "drf"},
        ),
        (
            {"frontend": "react", "mobile": "flutter", "backend": "fastapi"},
            {},
            False,
            {"base", "reactjs", "flutter", "fastapi"},
        ),
        (
            {"frontend": "react", "mobile": "unknown", "backend": "fastapi"},
            {"rag": True},
            False,
            {"base", "reactjs", "fastapi", "rag"},
        ),
        (
            {"frontend": "nextjs", "mobile": "unknown", "backend": "django-drf"},
            {"webscraping": True},
            False,
            {"base", "nextjs", "drf", "webscraping"},
        ),
        (
            {
                "frontend": "react",
                "mobile": "unknown",
                "backend": "fastapi",
                "deployment": "aws",
            },
            {},
            True,
            {"base", "reactjs", "fastapi", "aws"},
        ),
    ],
)
def test_select_pack_matrix(
    frameworks: dict[str, str],
    capabilities: dict[str, bool],
    deployment: bool,
    expected: set[str],
) -> None:
    assert set(
        select_pack_names(frameworks, capabilities, include_deployment=deployment)
    ) == expected


def test_aws_is_not_selected_merely_because_prd_records_it() -> None:
    frameworks = {
        "frontend": "react",
        "mobile": "unknown",
        "backend": "fastapi",
        "deployment": "aws",
    }
    assert "aws" not in select_pack_names(frameworks, {}, include_deployment=False)


def test_missing_choices_are_exact() -> None:
    assert missing_framework_choices(
        {
            "frontend": "unknown",
            "mobile": "unknown",
            "backend": "unknown",
        }
    ) == ["client: react, nextjs, or flutter", "backend: django-drf or fastapi"]


def _fake_workflow(root: Path) -> None:
    config = root / "config"
    config.mkdir(parents=True)
    (config / "framework-packs.json").write_text(
        json.dumps(
            {
                "packs": {
                    "django-drf": {"path": "drf"},
                    "fastapi": {"path": "fastapi"},
                    "flutter": {"path": "flutter"},
                    "nextjs": {"path": "nextjs"},
                    "react": {"path": "reactjs"},
                },
                "capability_packs": {
                    "rag": {"path": "rag"},
                    "webscraping": {"path": "webscraping"},
                },
            }
        )
    )


def _initialize_fake_pack(workflow: Path, name: str) -> None:
    pack = workflow / name
    (pack / ".git").mkdir(parents=True)
    for relative in (
        "AGENTS.md",
        "agents/catalog.json",
        "skills/catalog.json",
        "hooks/lifecycle.json",
        "rules/project-structure.json",
    ):
        path = pack / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else f"# {name}\n")


def test_reconcile_initializes_only_selected_and_preserves_unused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow = tmp_path / "agents"
    project.mkdir()
    _fake_workflow(workflow)
    prd = project / "PRD.md"
    prd.write_text("# Product\n")

    for name in ("base", "drf", "reactjs", "rag"):
        _initialize_fake_pack(workflow, name)

    calls: list[list[str]] = []

    def runner(_directory: Path, arguments: list[str]) -> tuple[int, str]:
        calls.append(arguments)
        if arguments[:2] == ["rev-parse", "HEAD"]:
            return 0, "workflow-commit"
        if arguments[:2] == ["ls-files", "--stage"]:
            return 0, "160000 pack-commit 0\tpack"
        return 0, ""

    manifest = reconcile_selected_packs(
        project,
        prd,
        {
            "frontend": "react",
            "mobile": "unknown",
            "backend": "django-drf",
            "deployment": "unknown",
        },
        {"rag": False, "webscraping": False},
        root=workflow,
        runner=runner,
    )

    assert {item["name"] for item in manifest["selected_packs"]} == {
        "base",
        "drf",
        "reactjs",
    }
    assert manifest["unused_initialized_packs"] == ["rag"]
    assert not [call for call in calls if call[:2] == ["submodule", "update"]]
    assert json.loads((project / ".ai" / "selected-packs.json").read_text()) == manifest


def test_reconcile_lazily_initializes_new_capability_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow = tmp_path / "agents"
    project.mkdir()
    _fake_workflow(workflow)
    prd = project / "PRD.md"
    prd.write_text("# Product\n\nRAG: Required\n")
    for name in ("base", "fastapi", "reactjs"):
        _initialize_fake_pack(workflow, name)

    initialized: list[str] = []

    def runner(_directory: Path, arguments: list[str]) -> tuple[int, str]:
        if arguments[:3] == ["submodule", "update", "--init"]:
            paths = arguments[4:]
            initialized.extend(paths)
            for name in paths:
                _initialize_fake_pack(workflow, name)
            return 0, ""
        return 0, ""

    manifest = reconcile_selected_packs(
        project,
        prd,
        {
            "frontend": "react",
            "mobile": "unknown",
            "backend": "fastapi",
            "deployment": "unknown",
        },
        {"rag": True, "webscraping": False},
        root=workflow,
        runner=runner,
    )

    assert initialized == ["rag"]
    assert manifest["missing_selected_packs"] == []
    assert not (workflow / "drf" / ".git").exists()
    assert not (workflow / "webscraping" / ".git").exists()


def test_select_packs_cli_uses_prd_and_reports_no_missing_choices(tmp_path: Path) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Product\n\n"
        "Frontend framework: React\n"
        "Backend framework: Django REST Framework\n"
        "RAG: Not required\n"
        "Web scraping: Not required\n"
    )

    assert main(["select-packs", "--project", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / ".ai" / "selected-packs.json").read_text())
    assert {item["name"] for item in manifest["selected_packs"]} == {
        "base",
        "drf",
        "reactjs",
    }
    assert manifest["missing_selected_packs"] == []
    assert manifest["deployment_included"] is False
    assert selected_pack_status(tmp_path)["prd_hash_current"] is True
    (tmp_path / "PRD.md").write_text("# Changed product\n")
    assert selected_pack_status(tmp_path)["prd_hash_current"] is False


def test_reconcile_reports_submodule_initialization_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    workflow = tmp_path / "agents"
    project.mkdir()
    _fake_workflow(workflow)
    prd = project / "PRD.md"
    prd.write_text("# Product\n")

    def runner(_directory: Path, arguments: list[str]) -> tuple[int, str]:
        if arguments[:3] == ["submodule", "update", "--init"]:
            return 1, "authentication failed"
        return 0, ""

    with pytest.raises(RuntimeError, match="authentication failed"):
        reconcile_selected_packs(
            project,
            prd,
            {
                "frontend": "react",
                "mobile": "unknown",
                "backend": "fastapi",
                "deployment": "unknown",
            },
            {"rag": False, "webscraping": False},
            root=workflow,
            runner=runner,
        )


def test_lightweight_bootstrap_entrypoint_needs_no_workflow_state(tmp_path: Path) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Product\n\n"
        "Mobile framework: Flutter\n"
        "Backend framework: FastAPI\n"
        "RAG: Not required\n"
        "Web scraping: Not required\n"
    )

    assert lightweight_main(["--project", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / ".ai" / "selected-packs.json").read_text())
    assert {item["name"] for item in manifest["selected_packs"]} == {
        "base",
        "fastapi",
        "flutter",
    }
