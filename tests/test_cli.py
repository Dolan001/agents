import json
from pathlib import Path

from ai_workflow.cli import main
from ai_workflow.discovery import detect
from ai_workflow.pipeline import validate_control_plane


def test_detects_frameworks() -> None:
    assert detect(["apps/frontend/next.config.ts", "apps/backend/manage.py"]) == {
        "frontend": "nextjs",
        "backend": "django-drf",
        "reasons": ["Django manage.py detected"],
    }


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
    assert report["nodes"] == 24
    assert report["agentic_nodes"] == 14
