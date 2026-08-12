"""Validate generated targets against selected behavior-pack structure contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .model import utc_now


def validate_structure(project: Path, pack: Path, phase: str) -> dict[str, Any]:
    contract = read_json(pack / "rules" / "project-structure.json")
    if not isinstance(contract, dict):
        raise RuntimeError(f"framework structure contract is missing: {pack}")
    target_value = contract.get("target_root")
    required = contract.get("required_paths")
    required_directories = contract.get("required_directories", [])
    if (
        not isinstance(target_value, str)
        or not isinstance(required, list)
        or not isinstance(required_directories, list)
    ):
        raise RuntimeError(f"framework structure contract is invalid: {pack}")
    target = (project / target_value).resolve()
    if target != project and project not in target.parents:
        raise RuntimeError(f"framework target escapes project: {target_value}")
    missing = [
        relative
        for relative in required
        if not isinstance(relative, str) or not (target / relative).exists()
    ]
    wrong_type = []
    directory_set = set(required_directories)
    for relative in required:
        candidate = target / relative
        if not candidate.exists():
            continue
        if relative in directory_set and not candidate.is_dir():
            wrong_type.append(relative)
        if relative not in directory_set and not candidate.is_file():
            wrong_type.append(relative)
    report = {
        "phase": phase,
        "framework": contract.get("framework"),
        "target_root": target_value,
        "required_paths": required,
        "missing_paths": missing,
        "wrong_type_paths": wrong_type,
        "valid": not missing and not wrong_type,
        "checked_at": utc_now(),
    }
    write_json(project / ".ai" / "evidence" / "structure" / f"{phase}.json", report)
    if missing or wrong_type:
        raise RuntimeError(
            f"generated {phase} structure is invalid: missing={missing}, wrong_type={wrong_type}"
        )
    return report


def validate_monorepo(project: Path, contract_path: Path) -> dict[str, Any]:
    contract = read_json(contract_path)
    if not isinstance(contract, dict):
        raise RuntimeError("target monorepo contract is missing")
    files = contract.get("required_files")
    directories = contract.get("required_directories")
    if not isinstance(files, list) or not isinstance(directories, list):
        raise RuntimeError("target monorepo contract is invalid")
    missing_files = [item for item in files if not (project / item).is_file()]
    missing_directories = [item for item in directories if not (project / item).is_dir()]
    report = {
        "valid": not missing_files and not missing_directories,
        "missing_files": missing_files,
        "missing_directories": missing_directories,
        "checked_at": utc_now(),
    }
    write_json(project / ".ai" / "evidence" / "structure" / "monorepo.json", report)
    if missing_files or missing_directories:
        raise RuntimeError(
            "target monorepo structure is incomplete: "
            f"files={missing_files}, directories={missing_directories}"
        )
    return report
