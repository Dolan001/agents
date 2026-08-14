"""Validate generated targets against selected behavior-pack structure contracts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .io import read_json, write_json
from .model import utc_now


def _domain_instances(target: Path, contract: dict[str, Any]) -> list[Path]:
    pattern = contract.get("domain_path_pattern")
    minimum = contract.get("minimum_domain_instances")
    if not isinstance(pattern, str) or "<domain>" not in pattern or not isinstance(minimum, int):
        return []
    prefix, suffix = pattern.split("<domain>", 1)
    parent = target / prefix.rstrip("/") if prefix else target
    excluded = contract.get("domain_excluded_paths", [])
    if not isinstance(excluded, list) or not all(isinstance(item, str) for item in excluded):
        raise RuntimeError("framework domain exclusions are invalid")
    excluded_paths = {(target / item).resolve() for item in excluded}
    instances = [
        child
        for child in sorted(parent.iterdir())
        if child.is_dir()
        and child.resolve() not in excluded_paths
        and (not suffix or child.as_posix().endswith(suffix))
        and not child.name.startswith((".", "__"))
    ] if parent.is_dir() else []
    if len(instances) < minimum:
        raise RuntimeError(
            f"generated backend structure requires at least {minimum} domain instance(s)"
        )
    return instances


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
    domain_instances: list[str] = []
    missing_domain_paths: list[str] = []
    wrong_type_domain_paths: list[str] = []
    instances = _domain_instances(target, contract)
    domain_required = contract.get("required_domain_paths", [])
    domain_directories = contract.get("required_domain_directories", [])
    if not isinstance(domain_required, list) or not isinstance(domain_directories, list):
        raise RuntimeError("framework domain structure contract is invalid")
    domain_directory_set = set(domain_directories)
    for instance in instances:
        instance_name = instance.relative_to(target).as_posix()
        domain_instances.append(instance_name)
        for relative in domain_required:
            if not isinstance(relative, str):
                missing_domain_paths.append(f"{instance_name}/<invalid>")
                continue
            candidate = instance / relative
            reported = f"{instance_name}/{relative}"
            if not candidate.exists():
                missing_domain_paths.append(reported)
            elif relative in domain_directory_set and not candidate.is_dir():
                wrong_type_domain_paths.append(reported)
            elif relative not in domain_directory_set and not candidate.is_file():
                wrong_type_domain_paths.append(reported)
    report = {
        "phase": phase,
        "framework": contract.get("framework"),
        "target_root": target_value,
        "required_paths": required,
        "missing_paths": missing,
        "wrong_type_paths": wrong_type,
        "domain_instances": domain_instances,
        "missing_domain_paths": missing_domain_paths,
        "wrong_type_domain_paths": wrong_type_domain_paths,
        "valid": not missing
        and not wrong_type
        and not missing_domain_paths
        and not wrong_type_domain_paths,
        "checked_at": utc_now(),
    }
    write_json(project / ".ai" / "evidence" / "structure" / f"{phase}.json", report)
    if missing or wrong_type or missing_domain_paths or wrong_type_domain_paths:
        raise RuntimeError(
            f"generated {phase} structure is invalid: missing={missing}, wrong_type={wrong_type}, "
            f"domain_missing={missing_domain_paths}, domain_wrong_type={wrong_type_domain_paths}"
        )
    return report


def validate_database_evidence(
    project: Path, schema_path: Path, expected_framework: str
) -> dict[str, Any]:
    evidence_path = project / ".ai" / "evidence" / "database-verification.json"
    evidence = read_json(evidence_path)
    schema = read_json(schema_path)
    if not isinstance(evidence, dict) or not isinstance(schema, dict):
        raise RuntimeError("database verification evidence or schema is missing")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(evidence),
        key=lambda item: list(item.path),
    )
    if errors:
        summaries = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise RuntimeError(f"database verification evidence is invalid: {summaries}")
    if evidence["framework"] != expected_framework:
        raise RuntimeError(
            "database verification framework does not match the selected backend"
        )
    forbidden_keys = {"database_url", "dsn", "password", "secret", "token"}
    credential_url = re.compile(r"postgres(?:ql)?(?:\+[^:]*)?://[^/@:]+:[^/@]+@", re.I)

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in forbidden_keys:
                    raise RuntimeError(
                        "database verification evidence contains a secret-bearing key"
                    )
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)
        elif isinstance(value, str) and credential_url.search(value):
            raise RuntimeError("database verification evidence contains connection credentials")

    inspect(evidence)
    return evidence


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
