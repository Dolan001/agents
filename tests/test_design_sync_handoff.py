import hashlib
import json

import pytest

from ai_workflow.design import approve_generated_html, validate_html_approval
from ai_workflow.design_fidelity import (
    record_verified_baseline_update,
    verified_baseline_update_current,
)


def prepare(tmp_path, monkeypatch):
    generated = tmp_path / "HTML/generated/index.html"
    generated.parent.mkdir(parents=True)
    generated.write_text("<h1>Original</h1>")
    evidence = tmp_path / ".ai/evidence/design"
    evidence.mkdir(parents=True)
    (evidence / "verification.json").write_text('{"verified": true}')
    (evidence / "source-checks.json").write_text(json.dumps({
        "status": "passed", "exit_code": 0,
        "output_hashes": {"HTML/generated/index.html": hashlib.sha256(
            generated.read_bytes()
        ).hexdigest()},
    }))
    approve_generated_html(tmp_path)
    (tmp_path / "HTML/approved/index.html").write_text("<h1>Corrected runtime reference</h1>")
    verification = tmp_path / ".ai/evidence/design-fidelity/frontend/verification.json"
    verification.parent.mkdir(parents=True)
    verification.write_text('{"verified": true, "baseline_changed": true}')

    def validated(*args, **kwargs):
        assert kwargs["allow_baseline_update"] is True
        return {"verified": True, "baseline_changed": True}

    monkeypatch.setattr("ai_workflow.design_fidelity.validate_design_fidelity_evidence", validated)
    return verification


@pytest.mark.parametrize("changed", [
    "HTML/approved/index.html", "HTML/generated/index.html", "PRD.md",
    ".ai/evidence/design-fidelity/frontend/verification.json",
])
def test_verified_handoff_binds_sources_and_review(tmp_path, monkeypatch, changed):
    prepare(tmp_path, monkeypatch)
    original_review = (tmp_path / ".ai/evidence/design/verification.json").read_bytes()
    assert not verified_baseline_update_current(tmp_path)
    record_verified_baseline_update(tmp_path, "frontend", "react")
    assert verified_baseline_update_current(tmp_path)
    assert validate_html_approval(tmp_path)["approved"] is True
    assert (tmp_path / ".ai/evidence/design/verification.json").read_bytes() == original_review
    (tmp_path / changed).write_text("changed")
    assert not verified_baseline_update_current(tmp_path)


def test_failed_independent_verification_cannot_update_approval(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    approval = tmp_path / ".ai/evidence/design/owner-approval.json"
    before = approval.read_bytes()

    def rejected(*args, **kwargs):
        raise RuntimeError("pixel verification failed")

    monkeypatch.setattr("ai_workflow.design_fidelity.validate_design_fidelity_evidence", rejected)
    with pytest.raises(RuntimeError, match="pixel verification failed"):
        record_verified_baseline_update(tmp_path, "frontend", "react")
    assert approval.read_bytes() == before
    assert not (tmp_path / ".ai/evidence/design/approved-baseline-sync.json").exists()


def test_authorized_recheck_can_finish_a_previously_repaired_baseline(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "ai_workflow.design_fidelity.validate_design_fidelity_evidence",
        lambda *args, **kwargs: {"verified": True, "baseline_changed": False},
    )
    record_verified_baseline_update(tmp_path, "frontend", "react")
    assert verified_baseline_update_current(tmp_path)
    assert validate_html_approval(tmp_path)["approved"] is True
