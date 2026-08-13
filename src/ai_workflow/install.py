"""Install thin, managed command entrypoints into a target project."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

MANAGED_MARKER = "managed-by: ai_workflow"
PLATFORMS = ("claude", "opencode", "codex")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _safe_destination(project: Path, relative: str) -> Path:
    destination = (project / relative).resolve()
    if project not in destination.parents:
        raise RuntimeError(f"command destination escapes project: {relative}")
    return destination


def _write_managed(path: Path, content: str, force: bool) -> str:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged"
        if MANAGED_MARKER not in existing and not force:
            raise RuntimeError(f"refusing to overwrite unmanaged file: {path}")
    _atomic_text(path, content)
    return "installed"


def install_entrypoints(
    project: Path,
    workflow_path: str = "ai_workflow",
    force: bool = False,
    platforms: tuple[str, ...] = PLATFORMS,
) -> dict[str, Any]:
    """Expose canonical workflow entrypoints to selected project clients."""
    unknown = sorted(set(platforms) - set(PLATFORMS))
    if unknown:
        raise RuntimeError(f"unsupported entrypoint platforms: {unknown}")
    root = Path(__file__).resolve().parents[2]
    source_commands = root / "commands"
    source_skills = root / "skills"
    command_names = sorted(path.stem for path in source_commands.glob("start-*.md"))
    command_names.extend(["resume-build", "workflow-status"])
    installed: list[str] = []
    unchanged: list[str] = []

    command_platforms = (
        (adapter, directory)
        for adapter, directory in (
            ("claude", ".claude/commands"),
            ("opencode", ".opencode/commands"),
        )
        if adapter in platforms
    )
    for adapter, directory in command_platforms:
        for name in command_names:
            source = source_commands / f"{name}.md"
            content = source.read_text(encoding="utf-8").replace("{{ADAPTER}}", adapter)
            content = content.replace("{{WORKFLOW_PATH}}", workflow_path)
            destination = _safe_destination(project, f"{directory}/{name}.md")
            result = _write_managed(destination, content, force)
            (installed if result == "installed" else unchanged).append(
                destination.relative_to(project).as_posix()
            )

    if "codex" in platforms:
        for name in command_names:
            source_dir = source_skills / name
            for filename in ("SKILL.md", "agents/openai.yaml"):
                source = source_dir / filename
                if not source.is_file():
                    raise RuntimeError(f"missing Codex skill source: {source}")
                content = source.read_text(encoding="utf-8")
                content = content.replace("{{WORKFLOW_PATH}}", workflow_path)
                if MANAGED_MARKER not in content:
                    content = content.rstrip() + f"\n\n<!-- {MANAGED_MARKER} -->\n"
                destination = _safe_destination(project, f".agents/skills/{name}/{filename}")
                result = _write_managed(destination, content, force)
                (installed if result == "installed" else unchanged).append(
                    destination.relative_to(project).as_posix()
                )

    manifest = {
        "version": 1,
        "workflow_path": workflow_path,
        "platforms": list(platforms),
        "commands": command_names,
        "installed": installed,
        "unchanged": unchanged,
    }
    return manifest
