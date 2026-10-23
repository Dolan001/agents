#!/usr/bin/env python3
"""Check the structure and basic traceability of a requirements source."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADINGS = (
    "Product goals and release scope",
    "Deliverables and framework choices",
    "Users, roles, and permissions",
    "Functional requirements",
    "Business rules and edge cases",
    "Data and privacy",
    "Experience and design requirements",
    "Non-functional requirements",
    "Structural requirements",
    "Acceptance scenarios and traceability",
    "Delivery and verification",
    "Assumptions and open decisions",
)
REGISTERS = {
    "Functional requirements": "FR",
    "Business rules and edge cases": "BR",
    "Non-functional requirements": "NFR",
    "Structural requirements": "SR",
    "Acceptance scenarios and traceability": "AC",
}
TARGET = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|seconds?|minutes?|hours?|days?|rps|rpm|users?|mb|gb)\b",
    re.I,
)


def sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\s*$", text))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip()] = text[match.end() : end].strip()
    return result


def validate(text: str) -> list[str]:
    errors: list[str] = []
    review_status = r"(?mi)^Review status:\s*(?:Pending user approval|Approved by user)\s*$"
    if not re.search(review_status, text):
        errors.append("missing review status")
    headings = re.findall(r"(?m)^## ([^\n]+)\s*$", text)
    if len(headings) != len(set(headings)):
        errors.append("duplicate second-level headings")
    present = [heading for heading in headings if heading in HEADINGS]
    if present != [heading for heading in HEADINGS if heading in present]:
        errors.append("required headings are out of order")
    parts = sections(text)
    for heading in HEADINGS:
        if not parts.get(heading):
            errors.append(f"missing or empty section: {heading}")
    ids: dict[str, list[str]] = {}
    for heading, prefix in REGISTERS.items():
        ids[prefix] = re.findall(rf"(?m)^\s*[-*]\s+({prefix}-\d{{3}})\b", parts.get(heading, ""))
        if not ids[prefix]:
            errors.append(f"missing {prefix} entries in {heading}")
        if len(ids[prefix]) != len(set(ids[prefix])):
            errors.append(f"duplicate {prefix} identifiers")
    acceptance = parts.get("Acceptance scenarios and traceability", "")
    ac_entries = list(re.finditer(r"(?m)^\s*[-*]\s+(AC-\d{3})\b", acceptance))
    mapped: set[str] = set()
    for index, match in enumerate(ac_entries):
        end = ac_entries[index + 1].start() if index + 1 < len(ac_entries) else len(acceptance)
        links = set(re.findall(r"\bFR-\d{3}\b", acceptance[match.end() : end]))
        if not links:
            errors.append(f"{match.group(1)} has no FR link")
        mapped.update(links)
    for identifier in ids["FR"]:
        if identifier not in mapped:
            errors.append(f"{identifier} has no acceptance scenario")
    for identifier in sorted(mapped - set(ids["FR"])):
        errors.append(f"acceptance scenario names missing {identifier}")
    if ids["NFR"] and not TARGET.search(parts.get("Non-functional requirements", "")):
        errors.append("non-functional requirements need a numeric, measurable target")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: check_requirements.py REQUIREMENTS.md", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        findings = validate(path.read_text(encoding="utf-8"))
    except OSError as error:
        print(error, file=sys.stderr)
        return 2
    for finding in findings:
        print(f"- {finding}")
    if findings:
        return 1
    print(f"Requirements structure and FR traceability pass: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
