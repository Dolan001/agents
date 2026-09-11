"""Deterministic design-input ingestion and routing."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .io import read_json, write_json
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


def approve_generated_html(project: Path) -> dict[str, Any]:
    """Bind explicit owner approval to the exact source-checked HTML draft."""
    generated = project / "HTML" / "generated"
    if not generated.is_dir():
        raise RuntimeError(
            "HTML/generated is missing; run $start-generatehtml before approving HTML"
        )
    files = sorted(path for path in generated.rglob("*") if path.is_file())
    if not files or not any(path.suffix.lower() in HTML_SUFFIXES for path in files):
        raise RuntimeError(
            "HTML/generated has no HTML draft; run $start-generatehtml before approving HTML"
        )
    if any(path.is_symlink() for path in generated.rglob("*")):
        raise RuntimeError("HTML/generated contains a symlink and cannot be approved safely")

    checks_path = project / ".ai" / "evidence" / "design" / "source-checks.json"
    checks = read_json(checks_path, {})
    expected = checks.get("output_hashes") if isinstance(checks, dict) else None
    if (
        not isinstance(checks, dict)
        or checks.get("status") != "passed"
        or checks.get("exit_code") != 0
        or not isinstance(expected, dict)
    ):
        raise RuntimeError("current HTML source checks have not passed; rerun $start-generatehtml")

    actual = {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }
    if expected != actual:
        raise RuntimeError(
            "HTML/generated changed after source checks; rerun $start-generatehtml before approval"
        )

    approved = project / "HTML" / "approved"
    staging = project / "HTML" / ".approved-workflow-staging"
    backup = project / "HTML" / ".approved-workflow-backup"
    for workflow_path in (staging, backup):
        if workflow_path.exists():
            shutil.rmtree(workflow_path)
    shutil.copytree(generated, staging)
    replaced = approved.exists()
    try:
        if replaced:
            approved.rename(backup)
        staging.rename(approved)
    except BaseException:
        if backup.exists() and not approved.exists():
            backup.rename(approved)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)

    routing = read_json(project / ".ai" / "design-inputs.json", {})
    mode = routing.get("mode") if isinstance(routing, dict) else None
    evidence = {
        "version": 1,
        "approved": True,
        "approved_at": utc_now(),
        "design_mode": mode or "unknown",
        "approval_method": "explicit --approve-html invocation after preview review",
        "source_checks": checks_path.relative_to(project).as_posix(),
        "source_hashes": actual,
        "approved_hashes": {
            path.relative_to(approved).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(approved.rglob("*"))
            if path.is_file()
        },
        "browser_evidence_claimed": False,
    }
    write_json(project / ".ai" / "evidence" / "design" / "owner-approval.json", evidence)
    return evidence
