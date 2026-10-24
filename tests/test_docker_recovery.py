"""Safety checks for approval-bound Docker storage recovery."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_workflow.docker_recovery import execute_recovery, inspect_recovery
from ai_workflow.io import read_json


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    current = tmp_path / "current"
    current.mkdir()
    old = tmp_path / "old"
    (old / ".ai").mkdir(parents=True)
    (old / ".ai" / "node-state.json").write_text("{}", encoding="utf-8")
    config = old / "compose.yaml"
    config.write_text("services: {}\n", encoding="utf-8")
    from ai_workflow.docker_recovery import _compose_name

    return current, config, _compose_name(old)


def _fake_docker(config: Path, name: str, calls: list[tuple[str, ...]], *, running: bool = False):
    def invoke(*args: str) -> str:
        calls.append(args)
        if args[:3] == ("compose", "ls", "--all"):
            return json.dumps([{"Name": name, "ConfigFiles": str(config)}])
        if args[:2] == ("container", "ls"):
            return "container-id\n"
        if args[:2] == ("network", "ls"):
            return "network-id\n"
        if args[:2] == ("image", "ls"):
            return "image-id\n"
        if args[:2] == ("volume", "ls"):
            return "volume-id\n"
        if args[0] == "inspect":
            return json.dumps([{"Created": "2020-01-01T00:00:00Z", "State": {"Running": running}}])
        if args[:2] == ("system", "df"):
            return "Docker usage"
        if args[1] == "rm":
            return args[-1]
        raise AssertionError(args)

    return invoke


def test_plan_only_offers_inactive_workflow_checkout(tmp_path: Path) -> None:
    current, config, name = _fixture(tmp_path)
    calls: list[tuple[str, ...]] = []
    with patch("ai_workflow.docker_recovery._docker", _fake_docker(config, name, calls)):
        plan = inspect_recovery(current)
    assert [item["name"] for item in plan["candidates"]] == [name]
    assert plan["candidates"][0]["volumes"] == ["volume-id"]
    assert read_json(current / ".ai/docker-recovery/plan.json")["plan_id"] == plan["plan_id"]


def test_running_project_is_not_offered(tmp_path: Path) -> None:
    current, config, name = _fixture(tmp_path)
    with patch(
        "ai_workflow.docker_recovery._docker",
        _fake_docker(config, name, [], running=True),
    ):
        assert inspect_recovery(current)["candidates"] == []


def test_approved_cleanup_preserves_volumes(tmp_path: Path) -> None:
    current, config, name = _fixture(tmp_path)
    calls: list[tuple[str, ...]] = []
    with patch("ai_workflow.docker_recovery._docker", _fake_docker(config, name, calls)):
        plan = inspect_recovery(current)
        result = execute_recovery(current, plan["plan_id"], name)
    assert result["deleted_volumes"] == []
    assert ("volume", "rm", "volume-id") not in calls
    assert ("container", "rm", "container-id") in calls
    assert ("network", "rm", "network-id") in calls
    assert ("image", "rm", "image-id") in calls


def test_volume_deletion_requires_explicit_option(tmp_path: Path) -> None:
    current, config, name = _fixture(tmp_path)
    calls: list[tuple[str, ...]] = []
    with patch("ai_workflow.docker_recovery._docker", _fake_docker(config, name, calls)):
        plan = inspect_recovery(current)
        result = execute_recovery(current, plan["plan_id"], name, delete_volumes=True)
    assert result["deleted_volumes"] == ["volume-id"]
    assert ("volume", "rm", "volume-id") in calls


def test_stale_plan_cannot_delete(tmp_path: Path) -> None:
    current, config, name = _fixture(tmp_path)
    calls: list[tuple[str, ...]] = []
    with patch("ai_workflow.docker_recovery._docker", _fake_docker(config, name, calls)):
        inspect_recovery(current)
        with pytest.raises(RuntimeError, match="missing or has changed"):
            execute_recovery(current, "incorrect-plan", name, delete_volumes=True)
    assert not any(args[1:2] == ("rm",) for args in calls)
