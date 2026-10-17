from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ai_workflow.provider_selection import (
    prd_provider,
    refresh_provider_projection,
    resolve_adapter,
    selected_provider,
)


def test_codex_is_default_without_selection(tmp_path: Path) -> None:
    assert selected_provider(tmp_path) == "codex"
    assert resolve_adapter(tmp_path, None, "codex-reviewed") == "codex-reviewed"
    assert resolve_adapter(tmp_path, "claude", "codex-reviewed") == "claude"


def test_saved_provider_is_selected(tmp_path: Path) -> None:
    selection = tmp_path / ".agent-bridge-state/selected-adapter"
    selection.parent.mkdir()
    selection.write_text("claude\n", encoding="utf-8")

    assert selected_provider(tmp_path) == "claude"
    assert resolve_adapter(tmp_path, None, "codex-reviewed") == "claude"


def test_prd_provider_is_used_without_local_selection(tmp_path: Path) -> None:
    (tmp_path / "PRD.md").write_text(
        "# Product Requirements Document\n\n## Build Directives\nAI workflow adapter: Cursor\n",
        encoding="utf-8",
    )

    assert prd_provider(tmp_path) == "cursor"
    assert resolve_adapter(tmp_path, None, "codex-reviewed") == "cursor"


def test_local_selection_overrides_prd_provider(tmp_path: Path) -> None:
    (tmp_path / "PRD.md").write_text(
        "## Build Directives\nAI workflow adapter: Cursor\n", encoding="utf-8"
    )
    selection = tmp_path / ".agent-bridge-state/selected-adapter"
    selection.parent.mkdir()
    selection.write_text("claude\n", encoding="utf-8")

    assert resolve_adapter(tmp_path, None, "codex-reviewed") == "claude"


def test_codex_does_not_require_optional_bridge(tmp_path: Path) -> None:
    with patch("ai_workflow.provider_selection.workflow_root", return_value=tmp_path):
        refresh_provider_projection(tmp_path, "codex")


def test_non_codex_requires_bridge(tmp_path: Path) -> None:
    with (
        patch("ai_workflow.provider_selection.workflow_root", return_value=tmp_path),
        pytest.raises(RuntimeError, match="submodule is required"),
    ):
        refresh_provider_projection(tmp_path, "claude")


def test_refresh_calls_bridge_without_changing_selection(tmp_path: Path) -> None:
    root = tmp_path / "agents"
    bridge = root / "agent-bridge/use-adapter"
    bridge.parent.mkdir(parents=True)
    bridge.write_text("#!/bin/sh\n", encoding="utf-8")
    completed = Mock(returncode=0, stdout="", stderr="")

    with (
        patch("ai_workflow.provider_selection.workflow_root", return_value=root),
        patch("ai_workflow.provider_selection.subprocess.run", return_value=completed) as run,
    ):
        refresh_provider_projection(tmp_path, "claude")

    argv = run.call_args.args[0]
    assert argv[0] == str(bridge)
    assert "--sync-only" in argv
    assert "--agents-root" in argv
