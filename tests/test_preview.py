"""Local preview binds only selected loopback ports and reuses a live preview."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ai_workflow import preview


def test_preview_starts_backend_and_frontend_on_available_ports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frontend = tmp_path / "apps/frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"scripts":{"dev":"vite"}}')
    (frontend / "package-lock.json").write_text("{}")
    (tmp_path / "compose.yaml").write_text("services:\n  backend:\n    image: example\n")
    ports = iter((49321, 49322))
    monkeypatch.setattr(preview, "_available_port", lambda preferred: next(ports))
    monkeypatch.setattr(preview, "_responds", lambda *args, **kwargs: True)
    calls: list[tuple[str, ...]] = []

    def compose(project: Path, override: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(preview, "_compose", compose)
    result = preview.start_local_preview(tmp_path, "react")
    assert result["url"] == "http://127.0.0.1:49322"
    assert result["backend_url"] == "http://127.0.0.1:49321"
    assert calls == [
        ("up", "-d", "--no-build", "backend"),
        ("up", "-d", "--no-build", "backend", "frontend"),
    ]
    override = json.loads((tmp_path / ".ai/local-preview/compose.yaml").read_text())
    assert override["services"]["backend"]["ports"] == ["127.0.0.1:49321:8000"]
    assert override["services"]["frontend"]["ports"] == ["127.0.0.1:49322:5173"]
    assert preview.start_local_preview(tmp_path, "react") == result
    assert len(calls) == 2


def test_backend_preview_starts_and_reuses_live_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "compose.yaml").write_text("services:\n  backend:\n    image: example\n")
    monkeypatch.setattr(preview, "_available_port", lambda preferred: 49200)
    monkeypatch.setattr(preview, "_responds", lambda *args, **kwargs: True)
    calls: list[tuple[str, ...]] = []

    def compose(project: Path, override: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(preview, "_compose", compose)
    first = preview.start_backend_preview(tmp_path)
    assert first["url"] == "http://127.0.0.1:49200"
    assert preview.start_backend_preview(tmp_path) == first
    assert calls == [("up", "-d", "--no-build", "backend")]
