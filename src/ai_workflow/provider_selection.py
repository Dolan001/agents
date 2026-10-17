"""Stable integration contract for the optional agent-bridge submodule."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .pipeline import workflow_root

PROVIDERS = ("codex", "claude", "opencode", "gemini", "cursor")
PROVIDER_LABELS = {
    "codex": "Codex",
    "claude": "Claude",
    "opencode": "OpenCode",
    "gemini": "Gemini",
    "cursor": "Cursor",
}
SELECTION = Path(".agent-bridge-state/selected-adapter")
_PRD_CANDIDATES = ("docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md")
_ADAPTER_DIRECTIVE = re.compile(
    r"(?m)^AI workflow adapter:[ \t]*(Codex|Claude|OpenCode|Gemini|Cursor)[ \t]*$"
)


def selected_provider(project: Path) -> str:
    path = project / SELECTION
    if not path.is_file():
        return "codex"
    provider = path.read_text(encoding="utf-8").strip()
    return provider if provider in PROVIDERS else "codex"


def prd_provider(project: Path) -> str | None:
    """Return the adapter declared by one unambiguous PRD, when present."""
    candidates = [
        project / relative
        for relative in _PRD_CANDIDATES
        if (project / relative).is_file()
    ]
    unique: dict[tuple[int, int], Path] = {}
    for candidate in candidates:
        stat = candidate.stat()
        unique[(stat.st_dev, stat.st_ino)] = candidate
    if len(unique) != 1:
        return None
    match = _ADAPTER_DIRECTIVE.search(next(iter(unique.values())).read_text(encoding="utf-8"))
    if not match:
        return None
    labels = {label: provider for provider, label in PROVIDER_LABELS.items()}
    return labels[match.group(1)]


def resolve_adapter(project: Path, explicit: str | None, codex_default: str) -> str:
    if explicit:
        return explicit
    selection = project / SELECTION
    if selection.is_file():
        local_provider = selected_provider(project)
        return codex_default if local_provider == "codex" else local_provider
    declared_provider = prd_provider(project)
    if declared_provider is None or declared_provider == "codex":
        return codex_default
    return declared_provider


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
