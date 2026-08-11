import json
from pathlib import Path

from ai_workflow.cli import main
from ai_workflow.discovery import detect
from ai_workflow.git import run_git
from ai_workflow.pipeline import node_cache_key, ready_phases, validate_control_plane


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
    assert report["nodes"] == 25
    assert report["agentic_nodes"] == 15
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
