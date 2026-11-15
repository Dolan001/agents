"""Approved design references must depict one comparable UI state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ai_workflow.design import approve_generated_html, capture_state, classify_design_inputs
from ai_workflow.execution import _artifact_ok


def test_capture_state_rejects_visible_state_gallery(tmp_path: Path) -> None:
    page = tmp_path / "chats.html"
    page.write_text(
        '<html data-design-state="success"><body>'
        '<article data-design-screen-state="success">Chats</article>'
        '<article data-design-screen-state="error">Retry</article>'
        "</body></html>"
    )
    with pytest.raises(RuntimeError, match="multiple visible UI states"):
        capture_state(page)


def test_legacy_state_card_gallery_is_rejected(tmp_path: Path) -> None:
    page = tmp_path / "chats.html"
    page.write_text(
        '<html><body><article class="state-card" data-state="success">Chats</article>'
        '<article class="state-card" data-state="error">Retry</article></body></html>'
    )
    with pytest.raises(RuntimeError, match="multiple visible UI states"):
        capture_state(page)


def test_capture_state_allows_one_visible_state_and_hidden_examples(tmp_path: Path) -> None:
    page = tmp_path / "chats.html"
    page.write_text(
        '<html data-design-state="success"><body>'
        '<input type="search"><article data-design-screen-state="success">Chats</article>'
        '<article hidden data-design-screen-state="error">Retry</article>'
        "</body></html>"
    )
    assert capture_state(page) == "success"


def test_capture_state_rejects_mismatched_marker(tmp_path: Path) -> None:
    page = tmp_path / "chats.html"
    page.write_text(
        '<html data-design-state="loading"><body>'
        '<article data-design-screen-state="success">Chats</article></body></html>'
    )
    with pytest.raises(RuntimeError, match="marker disagrees"):
        capture_state(page)


def test_html_approval_rejects_state_gallery_before_promotion(tmp_path: Path) -> None:
    page = tmp_path / "HTML/generated/chats.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<html data-design-state="success"><body>'
        '<article data-design-screen-state="success">Chats</article>'
        '<article data-design-screen-state="empty">No chats</article>'
        "</body></html>"
    )
    evidence = tmp_path / ".ai/evidence/design"
    evidence.mkdir(parents=True)
    (evidence / "verification.json").write_text('{"verified": true}')
    (evidence / "source-checks.json").write_text(json.dumps({
        "status": "passed", "exit_code": 0,
        "output_hashes": {
            "HTML/generated/chats.html": hashlib.sha256(page.read_bytes()).hexdigest(),
        },
    }))
    with pytest.raises(RuntimeError, match="multiple visible UI states"):
        approve_generated_html(tmp_path)
    assert not _artifact_ok(evidence / "verification.json", "verified-true")
    assert not (tmp_path / "HTML/approved").exists()


def test_new_project_requires_explicit_capture_state(tmp_path: Path) -> None:
    page = tmp_path / "HTML/generated/chats.html"
    page.parent.mkdir(parents=True)
    page.write_text("<html><body><h1>Chats</h1></body></html>")
    classify_design_inputs(tmp_path)
    evidence = tmp_path / ".ai/evidence/design"
    evidence.mkdir(parents=True)
    (evidence / "verification.json").write_text('{"verified": true}')
    (evidence / "source-checks.json").write_text(json.dumps({
        "status": "passed", "exit_code": 0,
        "output_hashes": {
            "HTML/generated/chats.html": hashlib.sha256(page.read_bytes()).hexdigest(),
        },
    }))
    with pytest.raises(RuntimeError, match="lacks a data-design-screen-state region"):
        approve_generated_html(tmp_path)
    assert not _artifact_ok(evidence / "verification.json", "verified-true")


def test_new_project_requires_a_marked_region_even_with_state_name(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text('<html data-design-state="default"><body><h1>Home</h1></body></html>')
    with pytest.raises(RuntimeError, match="lacks a data-design-screen-state region"):
        capture_state(page, require_explicit_region=True)


def test_component_library_states_do_not_count_as_screen_states(tmp_path: Path) -> None:
    page = tmp_path / "menu.html"
    page.write_text(
        '<html data-design-state="default"><body>'
        '<main data-design-screen-state="default">'
        '<button data-state="open">Menu</button><div data-state="closed">Dialog</div>'
        "</main></body></html>"
    )
    assert capture_state(page, require_explicit_region=True) == "default"


def test_capture_state_rejects_hidden_only_and_conflicting_markers(tmp_path: Path) -> None:
    page = tmp_path / "screen.html"
    page.write_text(
        '<html data-design-state="success"><body>'
        '<main hidden data-design-screen-state="success">Ready</main>'
        "</body></html>"
    )
    with pytest.raises(RuntimeError, match="no visible screen-state region"):
        capture_state(page, require_explicit_region=True)
    page.write_text(
        '<html data-design-state="success"><body data-design-state="error">'
        '<main data-design-screen-state="error">Retry</main></body></html>'
    )
    with pytest.raises(RuntimeError, match="conflicting capture states"):
        capture_state(page, require_explicit_region=True)
