"""Stable integration contract for the optional agent-bridge submodule."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .pipeline import workflow_root

PROVIDERS = ("codex", "claude", "opencode", "gemini")
SELECTION = Path(".agent-bridge-state/selected-adapter")


def selected_provider(project: Path) -> str:
    path = project / SELECTION
    if not path.is_file():
        return "codex"
    provider = path.read_text(encoding="utf-8").strip()
    return provider if provider in PROVIDERS else "codex"


def resolve_adapter(project: Path, explicit: str | None, codex_default: str) -> str:
    if explicit:
        return explicit
    provider = selected_provider(project)
    return codex_default if provider == "codex" else provider


def refresh_provider_projection(project: Path, adapter: str) -> None:
    provider = "codex" if adapter == "codex-reviewed" else adapter
    if provider not in PROVIDERS:
        return
    root = workflow_root()
    bridge = root / "agent-bridge" / "use-adapter"
    if not bridge.is_file():
        if provider == "codex":
            return
        raise RuntimeError(
            "the agent-bridge submodule is required for non-Codex adapters; run "
            "`git -C .agents submodule update --init agent-bridge`"
        )
    completed = subprocess.run(  # noqa: S603 - repository-owned bridge executable
        [
            str(bridge),
            provider,
            "--project",
            str(project),
            "--agents-root",
            str(root),
            "--sync-only",
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown bridge failure"
        raise RuntimeError(f"agent-bridge synchronization failed: {detail[-2000:]}")
