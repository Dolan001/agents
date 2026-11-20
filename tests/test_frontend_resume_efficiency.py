"""Resume frontend work from relevant inputs and validated partial design captures."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PIL import Image

from ai_workflow.design_fidelity import (
    approved_baseline,
    reusable_design_captures,
    validate_design_fidelity_comparison,
)
from ai_workflow.execution import _node_input_files
from ai_workflow.io import write_json
from ai_workflow.model import utc_now
from ai_workflow.pipeline import node_cache_key
from ai_workflow.visual_diff import compare_pixels


def test_foundation_audit_refresh_does_not_invalidate_verified_frontend_feature(
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps/frontend/src/features/auth/Login.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export const Login = () => null;\n")
    lock = tmp_path / "apps/frontend/package-lock.json"
    lock.write_text('{"lockfileVersion":3}')
    foundation = tmp_path / ".ai/evidence/frontend-foundation.json"
    foundation.parent.mkdir(parents=True)
    foundation.write_text('{"audit":"passed"}')
    feature = {
        "feature_id": "auth",
        "inputs": ["apps/frontend/src/features/auth/Login.tsx"],
        "allowed_paths": ["apps/frontend/src/features/auth/**"],
    }
    inputs = _node_input_files(tmp_path, "frontend", "implement-frontend-slices", feature)
    assert "apps/frontend/src/features/auth/Login.tsx" in inputs
    assert "apps/frontend/package-lock.json" in inputs
    assert ".ai/evidence/frontend-foundation.json" not in inputs
    first = node_cache_key(tmp_path, "frontend/implement-frontend-slices/auth", inputs)
    foundation.write_text('{"audit":"passed","checked_again":true}')
    assert node_cache_key(tmp_path, "frontend/implement-frontend-slices/auth", inputs) == first
    source.write_text("export const Login = () => 'changed';\n")
    assert node_cache_key(tmp_path, "frontend/implement-frontend-slices/auth", inputs) != first
    source.write_text("export const Login = () => null;\n")
    lock.write_text('{"lockfileVersion":3,"packages":{"changed":{}}}')
    assert node_cache_key(tmp_path, "frontend/implement-frontend-slices/auth", inputs) != first


def test_complete_capture_survives_interrupted_comparison_without_weakening_pixels(
    tmp_path: Path,
) -> None:
    approved = tmp_path / "HTML/approved/chats.html"
    approved.parent.mkdir(parents=True)
    approved.write_text(
        '<html data-design-state="success"><body><main>'
        '<a href="/chats/1">Open chat</a>'
        '<article data-design-screen-state="success">Chats</article>'
        '</main></body></html>'
    )
    source = tmp_path / "apps/frontend/src/App.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export const App = () => null;\n")
    root = tmp_path / ".ai/evidence/design-fidelity/frontend"
    root.mkdir(parents=True)
    baseline_hash, baseline_files = approved_baseline(tmp_path)
    cases = []
    for name in ("mobile", "tablet", "desktop"):
        capture = root / "captures"
        capture.mkdir(exist_ok=True)
        baseline_image = capture / f"{name}-baseline.png"
        rendered_image = capture / f"{name}-rendered.png"
        diff_image = root / "diffs" / f"{name}.png"
        metrics_path = root / "metrics" / f"{name}.json"
        diff_image.parent.mkdir(exist_ok=True)
        metrics_path.parent.mkdir(exist_ok=True)
        Image.new("RGBA", (240, 320), (10, 20, 30, 255)).save(baseline_image)
        Image.new("RGBA", (240, 320), (10, 20, 30, 255)).save(rendered_image)
        metrics = compare_pixels(baseline_image, rendered_image, diff_path=diff_image)
        # A different lossless PNG encoding must retain valid visual evidence.
        with Image.open(diff_image) as image:
            image.save(diff_image, format="PNG", compress_level=1)
        metrics["diff_sha256"] = hashlib.sha256(diff_image.read_bytes()).hexdigest()
        write_json(metrics_path, metrics)
        cases.append({
            "id": f"DF-CASE-{name.upper()}", "route": "/chats", "state": "success",
            "platform": "web",
            "viewport": {
                "name": name, "width": 240, "height": 320, "device_scale_factor": 1,
            },
            "baseline_html": approved.relative_to(tmp_path).as_posix(),
            "baseline_image": baseline_image.relative_to(tmp_path).as_posix(),
            "rendered_image": rendered_image.relative_to(tmp_path).as_posix(),
            "diff_image": diff_image.relative_to(tmp_path).as_posix(),
            "metrics": metrics_path.relative_to(tmp_path).as_posix(),
            "channel_tolerance": 0, "max_changed_ratio": 0, "masks": [],
        })
    write_json(root / "manifest.json", {
        "version": 1, "target": "frontend", "framework": "react",
        "baseline_sha256": baseline_hash, "baseline_files": baseline_files,
        "cases": cases, "generated_at": utc_now(),
    })
    write_json(root / "comparison.json", {
        "version": 1, "target": "frontend", "framework": "react",
        "baseline_sha256": baseline_hash, "mode": "repair", "aligned": True,
        "findings": [], "accepted_differences": [], "changed_paths": [],
        "summary": "All three pixel cases align with the approved baseline.",
        "verified": True, "checked_at": utc_now(),
    })
    (root / "repair-plan.md").write_text("No visual repair required.\n")
    assert validate_design_fidelity_comparison(tmp_path, "frontend", "react")["aligned"]
    assert reusable_design_captures(tmp_path, "frontend", "react") == {
        "manifest": ".ai/evidence/design-fidelity/frontend/manifest.json",
        "cases": 3, "passed": 3, "failed": 0, "largest_differences": [],
    }
    newest_capture = max(
        path.stat().st_mtime_ns for path in (root / "captures").glob("*.png")
    )
    os.utime(source, ns=(newest_capture + 1, newest_capture + 1))
    assert reusable_design_captures(tmp_path, "frontend", "react") is None
