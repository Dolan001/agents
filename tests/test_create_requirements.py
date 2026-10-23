"""Focused checks for the conversational requirements source contract."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _validator():
    path = (
        Path(__file__).resolve().parents[1]
        / "skills/create-requirements/scripts/check_requirements.py"
    )
    spec = spec_from_file_location("check_requirements", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def _valid_source() -> str:
    headings = (
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
    bodies = {
        "Functional requirements": "- FR-001: A member can send a message.",
        "Business rules and edge cases": "- BR-001: Only members can send.",
        "Non-functional requirements": "- NFR-001: 95% arrive within 2 seconds.",
        "Structural requirements": "- SR-001: The backend owns messages.",
        "Acceptance scenarios and traceability": (
            "- AC-001 (FR-001): Given a member, when they send, then the recipient sees it."
        ),
    }
    return "# Example\n\nReview status: Pending user approval\n\n" + "\n\n".join(
        f"## {heading}\n\n{bodies.get(heading, 'Defined for first release.')}"
        for heading in headings
    )


def test_requirements_register_and_traceability_pass() -> None:
    assert _validator()(_valid_source()) == []


def test_requirements_check_detects_missing_structure_and_mapping() -> None:
    source = _valid_source().replace(
        "- AC-001 (FR-001):", "- AC-001 (FR-999):"
    ).replace("- SR-001: The backend owns messages.", "No structure recorded.")
    findings = _validator()(source)
    assert "missing SR entries in Structural requirements" in findings
    assert "FR-001 has no acceptance scenario" in findings
    assert "acceptance scenario names missing FR-999" in findings
