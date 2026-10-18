"""Small, local quality loop: metadata-only telemetry, comparisons, reviewed lessons."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .io import append_jsonl, read_json, write_json
from .model import PHASES, utc_now


def record_attempt(
    project: Path,
    *,
    identity: str,
    adapter: str,
    agent: str,
    skills: list[str],
    prompt: str,
    elapsed_ms: int,
    result: dict[str, Any],
) -> None:
    """Record routing and size, never prompt contents or adapter output."""
    usage = result.get("usage")
    append_jsonl(
        project / ".ai" / "telemetry" / "attempts.jsonl",
        {
            "version": 1,
            "at": utc_now(),
            "identity": identity,
            "adapter": adapter,
            "agent": agent,
            "skills": skills,
            "prompt_characters": len(prompt),
            "elapsed_ms": elapsed_ms,
            "returncode": result.get("returncode"),
            "reported_usage": usage if isinstance(usage, dict) else None,
        },
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _prd_digest(project: Path, state: dict[str, Any]) -> str | None:
    for assumption in state.get("assumptions", []):
        if isinstance(assumption, str) and assumption.startswith("PRD source: "):
            path = (project / assumption.removeprefix("PRD source: ")).resolve()
            if path.is_file() and path.is_relative_to(project.resolve()):
                return hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def evaluate_manifest(path: Path) -> dict[str, Any]:
    """Compare separately completed runs; never start provider CLIs or modify projects."""
    manifest = read_json(path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise ValueError("evaluation manifest requires a cases list")
    if not manifest["cases"]:
        raise ValueError("evaluation manifest requires at least one case")
    cases = []
    for case in manifest["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("runs"), list):
            raise ValueError("each evaluation case requires runs")
        if len(case["runs"]) < 2:
            raise ValueError("each evaluation case requires at least two adapter runs")
        adapters = [run.get("adapter") for run in case["runs"] if isinstance(run, dict)]
        if len(set(adapters)) != len(case["runs"]):
            raise ValueError("each evaluation case requires distinct adapter names")
        required_nodes = case.get("required_nodes", [])
        if not isinstance(required_nodes, list) or not required_nodes or not all(
            isinstance(item, str) for item in required_nodes
        ):
            raise ValueError("required_nodes must name at least one checkpoint identity")
        rows = []
        for run in case["runs"]:
            if (
                not isinstance(run, dict)
                or not isinstance(run.get("adapter"), str)
                or not isinstance(run.get("project"), str)
            ):
                raise ValueError("each run requires adapter and project")
            project = (path.parent / run["project"]).resolve()
            state = read_json(project / ".ai" / "state.json")
            if not isinstance(state, dict):
                raise ValueError(f"workflow state is missing: {project}")
            checkpoint = read_json(project / ".ai" / "node-state.json", {})
            nodes = checkpoint.get("nodes", {}) if isinstance(checkpoint, dict) else {}
            if not isinstance(nodes, dict):
                nodes = {}
            attempts = _jsonl(project / ".ai" / "telemetry" / "attempts.jsonl")
            failures = _jsonl(project / ".ai" / "failures.jsonl")
            verified = sorted(
                key
                for key, value in nodes.items()
                if isinstance(value, dict) and value.get("status") == "VERIFIED"
            )
            rows.append(
                {
                    "adapter": run["adapter"],
                    "project": str(project),
                    "prd_sha256": _prd_digest(project, state),
                    "frameworks": state.get("frameworks", {}),
                    "capabilities": state.get("capabilities", {}),
                    "verified_nodes": verified,
                    "attempts": len(attempts),
                    "routing_matches": bool(attempts)
                    and all(item.get("adapter") == run["adapter"] for item in attempts),
                    "missing_required_nodes": sorted(set(required_nodes) - set(verified)),
                    "failed_attempts": sum(item.get("returncode") != 0 for item in attempts),
                    "failure_records": len(failures),
                    "prompt_characters": sum(item.get("prompt_characters", 0) for item in attempts),
                    "elapsed_ms": sum(item.get("elapsed_ms", 0) for item in attempts),
                }
            )
        comparable = (
            bool(rows[0]["prd_sha256"])
            and all(row["routing_matches"] for row in rows)
            and all(
                (row["prd_sha256"], row["frameworks"], row["capabilities"])
                == (rows[0]["prd_sha256"], rows[0]["frameworks"], rows[0]["capabilities"])
                for row in rows[1:]
            )
        )
        parity = (
            comparable
            and bool(rows[0]["verified_nodes"])
            and all(not row["missing_required_nodes"] for row in rows)
            and all(row["verified_nodes"] == rows[0]["verified_nodes"] for row in rows[1:])
        )
        cases.append(
            {
                "id": case.get("id", "unnamed"),
                "comparable": comparable,
                "checkpoint_parity": parity,
                "runs": rows,
            }
        )
    return {
        "version": 1,
        "all_comparable": all(case["comparable"] for case in cases),
        "all_checkpoint_parity": all(case["checkpoint_parity"] for case in cases),
        "cases": cases,
        "note": (
            "Character counts are a size proxy, not measured model tokens. "
            "Checkpoint parity is not behavioral equivalence."
        ),
    }


def propose_lessons(project: Path) -> list[dict[str, Any]]:
    """Turn failure metadata into review candidates; never promote automatically."""
    groups: dict[tuple[str, str], list[str]] = {}
    for failure in _jsonl(project / ".ai" / "failures.jsonl"):
        identity = failure.get("task_id", "")
        phase = identity.split("/", 1)[0] if isinstance(identity, str) else ""
        failure_class = failure.get("failure_class", "")
        if phase in PHASES and isinstance(failure_class, str) and failure_class:
            groups.setdefault((phase, failure_class), []).append(str(failure.get("failure_id", "")))
    proposals = []
    approved = read_json(project / ".ai" / "learning" / "approved.json", {"lessons": []})
    approved_ids = (
        {item.get("id") for item in approved.get("lessons", [])}
        if isinstance(approved, dict)
        else set()
    )
    for (phase, failure_class), ids in sorted(groups.items()):
        fingerprint = hashlib.sha256(f"{phase}:{failure_class}".encode()).hexdigest()[:12]
        proposal = {
            "id": f"LESSON-{fingerprint}",
            "phase": phase,
            "failure_class": failure_class,
            "count": len(ids),
            "evidence_ids": ids,
            "status": "approved" if f"LESSON-{fingerprint}" in approved_ids else "proposed",
        }
        proposals.append(proposal)
    write_json(
        project / ".ai" / "learning" / "proposals.json", {"version": 1, "proposals": proposals}
    )
    return proposals


def approve_lesson(project: Path, proposal_id: str, guidance: str) -> dict[str, Any]:
    """Only explicit human guidance can enter future prompts."""
    proposals = read_json(project / ".ai" / "learning" / "proposals.json", {})
    match = (
        next(
            (item for item in proposals.get("proposals", []) if item.get("id") == proposal_id), None
        )
        if isinstance(proposals, dict)
        else None
    )
    if match is None:
        raise ValueError("proposal not found; run propose-lessons first")
    guidance = guidance.strip()
    if not guidance or len(guidance) > 500 or re.search(r"[\x00-\x1f\x7f]", guidance):
        raise ValueError("guidance must be one line of 1–500 printable characters")
    target = project / ".ai" / "learning" / "approved.json"
    data = read_json(target, {"version": 1, "lessons": []})
    lessons = [item for item in data.get("lessons", []) if item.get("id") != proposal_id]
    lesson = {
        "id": proposal_id,
        "phase": match["phase"],
        "failure_class": match["failure_class"],
        "guidance": guidance,
        "approved_at": utc_now(),
        "evidence_ids": match["evidence_ids"],
    }
    lessons.append(lesson)
    write_json(target, {"version": 1, "lessons": lessons})
    return lesson


def approved_guidance(project: Path, phase: str) -> list[str]:
    data = read_json(project / ".ai" / "learning" / "approved.json", {})
    if not isinstance(data, dict):
        return []
    return [
        item["guidance"]
        for item in data.get("lessons", [])
        if isinstance(item, dict)
        and item.get("phase") == phase
        and isinstance(item.get("guidance"), str)
    ][:3]
