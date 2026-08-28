"""Conservative PRD extraction and reconciliation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import write_json

EXPLICIT_ID = re.compile(r"\b([A-Z][A-Z0-9]+-\d{3})\b")
HEADING = re.compile(r"^#{1,4}\s+(.+?)\s*$")
BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def parse_prd(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8")
    requirements: list[dict[str, Any]] = []
    explicit_bullets: list[tuple[str, str]] = []
    for raw_line in content.splitlines():
        bullet = BULLET.match(raw_line)
        if not bullet:
            continue
        description = bullet.group(1).strip()
        explicit = EXPLICIT_ID.search(description)
        if explicit:
            explicit_bullets.append((explicit.group(1), description))
    if explicit_bullets:
        seen: set[str] = set()
        for requirement_id, description in explicit_bullets:
            if requirement_id in seen:
                continue
            seen.add(requirement_id)
            requirements.append(
                {
                    "requirement_id": requirement_id,
                    "title": re.sub(EXPLICIT_ID, "", description).strip(" ():-,"),
                    "description": description,
                    "status": "NOT_STARTED",
                    "acceptance_criteria": [],
                    "evidence": [],
                    "remaining_tasks": [],
                }
            )
        return requirements

    # Compatibility fallback for a small informal PRD without stable IDs.
    category = "REQ"
    counters: dict[str, int] = {}
    for raw_line in content.splitlines():
        heading = HEADING.match(raw_line)
        if heading:
            words = re.findall(r"[A-Za-z]+", heading.group(1))
            if words:
                category = "".join(word[0] for word in words[:4]).upper()
            continue
        bullet = BULLET.match(raw_line)
        if not bullet:
            continue
        description = bullet.group(1).strip()
        explicit = EXPLICIT_ID.search(description)
        if explicit:
            requirement_id = explicit.group(1)
        else:
            counters[category] = counters.get(category, 0) + 1
            requirement_id = f"{category}-{counters[category]:03d}"
        requirements.append(
            {
                "requirement_id": requirement_id,
                "title": re.sub(EXPLICIT_ID, "", description).strip(" :-"),
                "description": description,
                "status": "NOT_STARTED",
                "acceptance_criteria": [],
                "evidence": [],
                "remaining_tasks": [],
            }
        )
    if not requirements:
        raise RuntimeError("PRD must contain at least one Markdown bullet requirement")
    return requirements


def reconcile(requirements: list[dict[str, Any]], files: list[str]) -> list[dict[str, Any]]:
    searchable = " ".join(files).lower()
    for requirement in requirements:
        words = [
            word.lower()
            for word in re.findall(r"[A-Za-z][A-Za-z0-9_]+", requirement["title"])
            if len(word) > 3
        ]
        hits = [word for word in words if word in searchable]
        if hits:
            requirement["status"] = "IMPLEMENTED_UNVERIFIED"
            requirement["evidence"] = [
                {
                    "kind": "source-name",
                    "path": "<repository-map>",
                    "result": f"matched: {', '.join(hits)}",
                }
            ]
            requirement["remaining_tasks"] = ["Verify acceptance criteria with suitable tests."]
        else:
            requirement["remaining_tasks"] = ["Plan and implement the requirement."]
    return requirements


def save_requirement_outputs(project: Path, requirements: list[dict[str, Any]]) -> None:
    generated = project / "docs" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    write_json(generated / "requirements.json", {"version": 1, "requirements": requirements})
    matrix = [
        "# Requirement matrix",
        "",
        "| ID | Requirement | Status |",
        "|---|---|---|",
    ]
    matrix.extend(
        f"| {item['requirement_id']} | {item['title'].replace('|', '/')} | {item['status']} |"
        for item in requirements
    )
    (generated / "requirement-matrix.md").write_text("\n".join(matrix) + "\n", encoding="utf-8")
