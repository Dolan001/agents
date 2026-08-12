"""Deterministic design-input ingestion and routing."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .io import write_json
from .model import utc_now

HTML_SUFFIXES = {".html", ".htm"}
SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DESIGN_SUFFIXES = {".fig", ".svg", ".pdf"}


def _validate_content(path: Path, expected: set[str]) -> None:
    if path.stat().st_size == 0:
        raise RuntimeError(f"design input is empty: {path}")
    if expected != SCREENSHOT_SUFFIXES:
        return
    suffix = path.suffix.lower()
    prefix = path.read_bytes()[:16]
    valid = (
        suffix == ".png"
        and prefix.startswith(b"\x89PNG\r\n\x1a\n")
        or suffix in {".jpg", ".jpeg"}
        and prefix.startswith(b"\xff\xd8\xff")
        or suffix == ".webp"
        and prefix.startswith(b"RIFF")
        and prefix[8:12] == b"WEBP"
    )
    if not valid:
        raise RuntimeError(f"screenshot content does not match its extension: {path}")


def _inside(project: Path, value: str) -> Path:
    candidate = Path(value)
    path = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
    if path != project and project not in path.parents:
        raise RuntimeError(f"design input must be inside the target project: {value}")
    if not path.is_file():
        raise RuntimeError(f"design input does not exist: {path}")
    return path


def ingest_design_inputs(
    project: Path, html: list[str] | None = None, screenshots: list[str] | None = None
) -> list[str]:
    """Copy explicitly supplied inputs into HTML/source and return their target paths."""
    destination = project / "HTML" / "source"
    destination.mkdir(parents=True, exist_ok=True)
    ingested: list[str] = []
    for expected, values in ((HTML_SUFFIXES, html or []), (SCREENSHOT_SUFFIXES, screenshots or [])):
        for value in values:
            source = _inside(project, value)
            if source.suffix.lower() not in expected:
                expected_text = ", ".join(sorted(expected))
                raise RuntimeError(
                    f"unexpected design input type for {source}: expected {expected_text}"
                )
            _validate_content(source, expected)
            target = destination / source.name
            if source != target.resolve():
                if target.exists() and target.read_bytes() != source.read_bytes():
                    raise RuntimeError(f"design input name collision: {target.name}")
                shutil.copy2(source, target)
            ingested.append(target.relative_to(project).as_posix())
    return sorted(set(ingested))


def classify_design_inputs(project: Path) -> dict[str, Any]:
    source = project / "HTML" / "source"
    assets = sorted(path for path in source.rglob("*") if path.is_file()) if source.is_dir() else []
    html = [path for path in assets if path.suffix.lower() in HTML_SUFFIXES]
    screenshots = [path for path in assets if path.suffix.lower() in SCREENSHOT_SUFFIXES]
    design_files = [path for path in assets if path.suffix.lower() in DESIGN_SUFFIXES]
    for path in html:
        _validate_content(path, HTML_SUFFIXES)
    for path in screenshots:
        _validate_content(path, SCREENSHOT_SUFFIXES)
    for path in design_files:
        _validate_content(path, DESIGN_SUFFIXES)
    if html:
        mode = "html_supplied"
        action = "validate_and_approve_supplied_html"
    elif screenshots or design_files:
        mode = "screenshot_supplied"
        action = "generate_html_from_visual_evidence_and_prd"
    else:
        mode = "prd_only"
        action = "generate_html_from_prd"

    def describe(path: Path) -> dict[str, str | int]:
        return {
            "path": path.relative_to(project).as_posix(),
            "media_type": path.suffix.lower().removeprefix("."),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    report = {
        "version": 1,
        "mode": mode,
        "required_action": action,
        "html": [describe(path) for path in html],
        "screenshots": [describe(path) for path in screenshots],
        "design_files": [describe(path) for path in design_files],
        "precedence": ["html", "screenshots_or_design", "prd"],
        "classified_at": utc_now(),
    }
    write_json(project / ".ai" / "design-inputs.json", report)
    return report
