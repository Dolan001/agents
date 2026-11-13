"""Opt-in static reuse cannot suppress live checks or changed inputs."""

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import ai_workflow.commands as commands
from ai_workflow.pipeline import workflow_root


def _manifest(project: Path, *, cached: bool) -> None:
    specification = {
        "argv": [sys.executable, "-c", "print('passed')"],
        "cwd": ".",
    }
    if cached:
        specification["cache"] = {"mode": "static", "read_only": True, "inputs": ["src/check.py"]}
    target = project / ".ai/test-commands.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"version": 1, "commands": {"frontend": [specification]}}))


def test_static_check_reuses_only_unchanged_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src/check.py"
    source.parent.mkdir()
    source.write_text("first")
    _manifest(tmp_path, cached=True)
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "passed", "")

    monkeypatch.setattr(commands.subprocess, "run", run)
    first = commands.run_command_groups(tmp_path, ["frontend"])
    second = commands.run_command_groups(tmp_path, ["frontend"])
    assert first["results"][0]["cached"] is False
    assert second["results"][0]["cached"] is True
    assert len(calls) == 1
    source.write_text("second")
    changed = commands.run_command_groups(tmp_path, ["frontend"])
    assert changed["results"][0]["cached"] is False
    assert len(calls) == 2
    unrelated = tmp_path / "src/other.py"
    unrelated.write_text("new input")
    conservative = commands.run_command_groups(tmp_path, ["frontend"])
    assert conservative["results"][0]["cached"] is False
    assert len(calls) == 3
    monkeypatch.setenv("WORKFLOW_CHECK_FLAG", "changed")
    changed_environment = commands.run_command_groups(tmp_path, ["frontend"])
    assert changed_environment["results"][0]["cached"] is False
    assert len(calls) == 4


def test_live_command_never_reuses_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _manifest(tmp_path, cached=False)
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "passed", "")

    monkeypatch.setattr(commands.subprocess, "run", run)
    commands.run_command_groups(tmp_path, ["frontend"])
    commands.run_command_groups(tmp_path, ["frontend"])
    assert len(calls) == 2


def test_static_cache_rejects_missing_inputs(tmp_path: Path) -> None:
    _manifest(tmp_path, cached=True)
    with pytest.raises(RuntimeError, match="has no files"):
        commands.run_command_groups(tmp_path, ["frontend"])


def test_phase_gate_forces_fresh_static_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src/check.py"
    source.parent.mkdir()
    source.write_text("stable")
    _manifest(tmp_path, cached=True)
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "passed", "")

    monkeypatch.setattr(commands.subprocess, "run", run)
    commands.run_command_groups(tmp_path, ["frontend"])
    fresh = commands.run_command_groups(tmp_path, ["frontend"], require_fresh=True)
    assert len(calls) == 2
    assert fresh["results"][0]["cached"] is False


def test_failed_static_check_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src/check.py"
    source.parent.mkdir()
    source.write_text("unchanged")
    _manifest(tmp_path, cached=True)
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "failed", "")

    monkeypatch.setattr(commands.subprocess, "run", run)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="approved command failed"):
            commands.run_command_groups(tmp_path, ["frontend"])
    assert len(calls) == 2


def test_all_executables_are_checked_before_first_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / ".ai/test-commands.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "commands": {
                    "frontend": [
                        {"argv": [sys.executable, "-c", "pass"], "cwd": "."},
                        {"argv": ["missing-workflow-tool"], "cwd": "."},
                    ]
                },
            }
        )
    )
    calls = []
    monkeypatch.setattr(commands.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(RuntimeError, match="command executable unavailable"):
        commands.run_command_groups(tmp_path, ["frontend"])
    assert calls == []


def test_only_declared_read_only_checks_run_in_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src/check.py"
    source.parent.mkdir()
    source.write_text("stable")
    target = tmp_path / ".ai/test-commands.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "commands": {
                    "frontend": [
                        {
                            "argv": [sys.executable, "-c", f"print({index})"],
                            "cwd": ".",
                            "parallel_safe": True,
                            "cache": {
                                "mode": "static",
                                "read_only": True,
                                "inputs": ["src/check.py"],
                            },
                        }
                        for index in (1, 2)
                    ]
                },
            }
        )
    )
    barrier = threading.Barrier(2)

    def run(*args, **kwargs):
        barrier.wait(timeout=2)
        return subprocess.CompletedProcess(args, 0, "passed", "")

    monkeypatch.setattr(commands.subprocess, "run", run)
    report = commands.run_command_groups(tmp_path, ["frontend"])
    assert report["passed"] is True
    assert [result["index"] for result in report["results"]] == [0, 1]


def test_missing_runtime_is_recorded_without_claiming_a_test_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manifest(tmp_path, cached=False)
    monkeypatch.setattr(
        commands.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 1, "", "ModuleNotFoundError: No module named 'jsonschema'"
        ),
    )
    with pytest.raises(RuntimeError, match="approved command failed"):
        commands.run_command_groups(tmp_path, ["frontend"])
    report = json.loads((tmp_path / "artifacts/tests/command-results.json").read_text())
    assert report["passed"] is False
    assert report["results"][0]["failure_kind"] == "missing_dependency"


def test_static_parallel_policy_is_schema_checked(tmp_path: Path) -> None:
    source = tmp_path / "src/check.py"
    source.parent.mkdir()
    source.write_text("stable")
    _manifest(tmp_path, cached=True)
    manifest = json.loads((tmp_path / ".ai/test-commands.json").read_text())
    schema = json.loads((workflow_root() / "schemas/test-commands.schema.json").read_text())
    validator = Draft202012Validator(schema)
    assert list(validator.iter_errors(manifest)) == []
    manifest["commands"]["frontend"][0]["cache"]["read_only"] = False
    assert list(validator.iter_errors(manifest))
