"""Load and validate the repository-owned workflow control plane."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .io import read_json
from .model import PHASES


def workflow_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _owned_path(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise RuntimeError(f"pipeline path escapes workflow repository: {value}")
    return candidate


def validate_control_plane(root: Path | None = None) -> dict[str, Any]:
    repository = (root or workflow_root()).resolve()
    config_path = repository / "config" / "pipeline.json"
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise RuntimeError(f"pipeline configuration is missing: {config_path}")

    order = config.get("phase_order")
    if order != list(PHASES):
        raise RuntimeError("pipeline phase order does not match the workflow state model")
    phases = config.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(PHASES):
        raise RuntimeError("pipeline configuration must define every workflow phase exactly once")

    groups = config.get("execution_groups")
    if not isinstance(groups, list) or not all(isinstance(group, list) for group in groups):
        raise RuntimeError("pipeline execution_groups must be a list of phase lists")
    flattened = [phase for group in groups for phase in group]
    if len(flattened) != len(set(flattened)) or set(flattened) != set(PHASES):
        raise RuntimeError("execution groups must schedule every phase exactly once")
    group_index = {phase: index for index, group in enumerate(groups) for phase in group}

    node_count = 0
    agentic_count = 0
    for phase in PHASES:
        entry = phases[phase]
        if not isinstance(entry, dict):
            raise RuntimeError(f"invalid phase entry: {phase}")
        loaded: dict[str, dict[str, Any]] = {}
        for kind in ("manifest", "blueprint", "gate"):
            relative = entry.get(kind)
            if not isinstance(relative, str):
                raise RuntimeError(f"{phase} does not declare a {kind}")
            path = _owned_path(repository, relative)
            payload = read_json(path)
            if not isinstance(payload, dict):
                raise RuntimeError(f"{phase} {kind} is missing or invalid: {relative}")
            loaded[kind] = payload

        if loaded["manifest"].get("name") != phase:
            raise RuntimeError(f"manifest name mismatch for phase: {phase}")
        if loaded["blueprint"].get("name") != phase:
            raise RuntimeError(f"blueprint name mismatch for phase: {phase}")
        if loaded["gate"].get("phase") != phase:
            raise RuntimeError(f"gate phase mismatch for phase: {phase}")
        if loaded["manifest"].get("gate") != entry["gate"]:
            raise RuntimeError(f"manifest gate mismatch for phase: {phase}")
        dependencies = entry.get("dependencies")
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str) and dependency in PHASES for dependency in dependencies
        ):
            raise RuntimeError(f"invalid dependencies for phase: {phase}")
        if loaded["manifest"].get("prerequisites") != dependencies:
            raise RuntimeError(f"manifest dependencies mismatch for phase: {phase}")
        if any(group_index[dependency] >= group_index[phase] for dependency in dependencies):
            raise RuntimeError(f"dependency is not scheduled before phase: {phase}")

        nodes = loaded["blueprint"].get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise RuntimeError(f"blueprint has no nodes: {phase}")
        identifiers: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                raise RuntimeError(f"invalid blueprint node in phase: {phase}")
            if node["id"] in identifiers:
                raise RuntimeError(f"duplicate node id in phase {phase}: {node['id']}")
            identifiers.add(node["id"])
            node_count += 1
            if node.get("type") == "agentic":
                agentic_count += 1
                if not all(isinstance(node.get(key), str) for key in ("agent", "required_output", "verification")):
                    raise RuntimeError(
                        f"agentic node lacks an artifact contract: {phase}/{node['id']}"
                    )
            elif node.get("type") != "deterministic":
                raise RuntimeError(f"unknown node type: {phase}/{node['id']}")

    return {
        "version": config.get("version"),
        "phase_order": list(PHASES),
        "execution_groups": groups,
        "phases": len(PHASES),
        "nodes": node_count,
        "agentic_nodes": agentic_count,
        "valid": True,
    }


def ready_phases(completed: set[str], running: set[str], root: Path | None = None) -> list[str]:
    """Return dependency-ready phases in configured critical-path order."""
    repository = (root or workflow_root()).resolve()
    config = read_json(repository / "config" / "pipeline.json")
    if not isinstance(config, dict):
        raise RuntimeError("pipeline configuration is missing")
    validate_control_plane(repository)
    phases = config["phases"]
    maximum = config["execution"]["maximum_parallel_tasks"]
    ready = [
        phase
        for phase in config["phase_order"]
        if phase not in completed
        and phase not in running
        and set(phases[phase]["dependencies"]) <= completed
    ]
    return ready[: max(0, maximum - len(running))]


def node_cache_key(root: Path, identity: str, inputs: list[str]) -> str:
    """Hash a node identity and its complete declared file inputs."""
    project = root.resolve()
    digest = hashlib.sha256(identity.encode())
    for relative in sorted(set(inputs)):
        candidate = (project / relative).resolve()
        if candidate != project and project not in candidate.parents:
            raise ValueError(f"cache input escapes project: {relative}")
        digest.update(b"\0path\0")
        digest.update(relative.encode())
        digest.update(b"\0content\0")
        if candidate.is_file():
            digest.update(candidate.read_bytes())
        else:
            digest.update(b"<missing>")
    return digest.hexdigest()
