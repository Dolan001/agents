"""Approval-bound cleanup of inactive workflow Docker projects."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .io import read_json, write_json

_WORKFLOW_PROJECT = re.compile(r"ai-[a-z0-9-]+-backend-[0-9a-f]{8}\Z")


def _docker(*args: str) -> str:
    executable = shutil.which("docker")
    if not executable:
        raise RuntimeError("Docker is unavailable; storage recovery cannot inspect projects")
    result = subprocess.run(  # noqa: S603 - fixed Docker executable and validated object IDs
        [executable, *args], capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode:
        raise RuntimeError(f"Docker storage inspection failed: {result.stderr.strip()[-500:]}")
    return result.stdout


def _compose_name(project: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project.resolve().name.lower()).strip("-")
    digest = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:8]
    return f"ai-{(slug or 'project')[:36]}-backend-{digest}"


def _ids(kind: str, project_name: str) -> list[str]:
    label = (
        f"ai.workflow.project={project_name}"
        if kind == "image"
        else f"com.docker.compose.project={project_name}"
    )
    args = [kind, "ls", "--filter", f"label={label}"]
    if kind == "container":
        args.append("--all")
    if kind == "image":
        args.append("--all")
    args.extend(["--quiet"])
    return sorted(set(_docker(*args).split()))


def _workflow_checkout(name: str, config_files: str) -> Path | None:
    if not _WORKFLOW_PROJECT.fullmatch(name):
        return None
    for item in config_files.split(","):
        config = Path(item.strip())
        if not config.is_file():
            continue
        for parent in config.resolve().parents:
            if (parent / ".ai" / "node-state.json").is_file() and _compose_name(parent) == name:
                return parent
    return None


def _candidate(name: str, checkout: Path) -> dict[str, Any] | None:
    containers = _ids("container", name)
    details = []
    if containers:
        details = json.loads(_docker("inspect", *containers))
    if any(item.get("State", {}).get("Running") for item in details):
        return None
    created = min((item.get("Created", "") for item in details), default="")
    return {
        "name": name,
        "checkout": str(checkout),
        "created": created,
        "containers": containers,
        "networks": _ids("network", name),
        "images": _ids("image", name),
        "volumes": _ids("volume", name),
    }


def inspect_recovery(project: Path) -> dict[str, Any]:
    """Inventory exact resources; age orders suggestions but never authorizes deletion."""
    current = _compose_name(project)
    raw = json.loads(_docker("compose", "ls", "--all", "--format", "json"))
    candidates = []
    for entry in raw:
        name = entry.get("Name", "")
        checkout = _workflow_checkout(name, entry.get("ConfigFiles", ""))
        if name == current or checkout is None:
            continue
        candidate = _candidate(name, checkout)
        if candidate and any(candidate[key] for key in ("containers", "images", "volumes")):
            candidates.append(candidate)
    candidates.sort(key=lambda item: (item["created"] or "9999", item["name"]))
    snapshot = {"current_project": current, "candidates": candidates}
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16]
    snapshot["plan_id"] = fingerprint
    snapshot["docker_disk_usage"] = _docker("system", "df")
    write_json(project / ".ai" / "docker-recovery" / "plan.json", snapshot)
    return snapshot


def execute_recovery(
    project: Path, plan_id: str, project_name: str, *, delete_volumes: bool = False
) -> dict[str, Any]:
    """Remove only approved, unchanged, stopped project objects, without force/prune."""
    saved = read_json(project / ".ai" / "docker-recovery" / "plan.json", {})
    if saved.get("plan_id") != plan_id:
        raise RuntimeError("Docker cleanup plan is missing or has changed; inspect it again")
    current = inspect_recovery(project)
    if current["plan_id"] != plan_id:
        raise RuntimeError("Docker resources changed since approval; review a fresh cleanup plan")
    candidate = next((item for item in current["candidates"] if item["name"] == project_name), None)
    if candidate is None:
        raise RuntimeError("approved project is not an inactive workflow-owned candidate")
    for object_id in candidate["containers"]:
        state = json.loads(_docker("inspect", object_id))[0]["State"]
        if state.get("Running"):
            raise RuntimeError("project started running; cleanup cancelled")
        _docker("container", "rm", object_id)
    for object_id in candidate["networks"]:
        _docker("network", "rm", object_id)
    for object_id in candidate["images"]:
        _docker("image", "rm", object_id)
    if delete_volumes:
        for object_id in candidate["volumes"]:
            _docker("volume", "rm", object_id)
    result = {
        "project": project_name,
        "deleted_containers": candidate["containers"],
        "deleted_networks": candidate["networks"],
        "deleted_images": candidate["images"],
        "deleted_volumes": candidate["volumes"] if delete_volumes else [],
        "docker_disk_usage_after": _docker("system", "df"),
    }
    write_json(project / ".ai" / "docker-recovery" / "result.json", result)
    return result
