"""Validate generated targets against selected behavior-pack structure contracts."""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .io import read_json, write_json
from .model import utc_now


def _contract_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise RuntimeError(f"framework structure path is unsafe: {relative}")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise RuntimeError(f"framework structure path escapes target: {relative}")
    return candidate


def _missing_or_wrong_type(
    root: Path, required: list[Any], directories: set[str]
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    wrong_type: list[str] = []
    for value in required:
        if not isinstance(value, str):
            missing.append("<invalid>")
            continue
        candidate = _contract_path(root, value)
        if not candidate.exists():
            missing.append(value)
        elif value in directories and not candidate.is_dir():
            wrong_type.append(value)
        elif value not in directories and not candidate.is_file():
            wrong_type.append(value)
    return missing, wrong_type


def _missing_path_sets(target: Path, contract: dict[str, Any]) -> list[str]:
    raw_sets = contract.get("required_path_sets", [])
    if not isinstance(raw_sets, list):
        raise RuntimeError("framework required path sets are invalid")
    missing: list[str] = []
    for raw_set in raw_sets:
        if not isinstance(raw_set, dict):
            raise RuntimeError("framework required path set is invalid")
        name = raw_set.get("name")
        alternatives = raw_set.get("alternatives")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(alternatives, list)
            or not alternatives
        ):
            raise RuntimeError("framework required path set is invalid")
        satisfied = False
        for alternative in alternatives:
            if not isinstance(alternative, list) or not alternative:
                raise RuntimeError(f"framework required path set is invalid: {name}")
            paths = [
                _contract_path(target, relative)
                for relative in alternative
                if isinstance(relative, str)
            ]
            if len(paths) != len(alternative):
                raise RuntimeError(f"framework required path set is invalid: {name}")
            if all(path.is_file() for path in paths):
                satisfied = True
                break
        if not satisfied:
            missing.append(name)
    return missing


def _conditional_domain_paths(
    instance: Path, contract: dict[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    raw_groups = contract.get("conditional_domain_groups", [])
    if not isinstance(raw_groups, list):
        raise RuntimeError("framework conditional domain groups are invalid")
    active: list[str] = []
    missing: list[str] = []
    wrong_type: list[str] = []
    for group in raw_groups:
        if not isinstance(group, dict):
            raise RuntimeError("framework conditional domain group is invalid")
        name = group.get("name")
        triggers = group.get("trigger_paths")
        required = group.get("required_paths")
        directories = group.get("required_directories", [])
        if (
            not isinstance(name, str)
            or not isinstance(triggers, list)
            or not all(isinstance(item, str) for item in triggers)
            or not isinstance(required, list)
            or not isinstance(directories, list)
            or not all(isinstance(item, str) for item in directories)
        ):
            raise RuntimeError("framework conditional domain group is invalid")
        if not any(_contract_path(instance, trigger).exists() for trigger in triggers):
            continue
        active.append(name)
        group_missing, group_wrong_type = _missing_or_wrong_type(
            instance, required, set(directories)
        )
        missing.extend(f"{name}:{relative}" for relative in group_missing)
        wrong_type.extend(f"{name}:{relative}" for relative in group_wrong_type)
    return active, missing, wrong_type


def _source_violations(target: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rules = contract.get("source_rules", [])
    if not isinstance(raw_rules, list):
        raise RuntimeError("framework source rules are invalid")
    violations: list[dict[str, Any]] = []
    for rule in raw_rules:
        if not isinstance(rule, dict):
            raise RuntimeError("framework source rule is invalid")
        rule_id = rule.get("id")
        globs = rule.get("globs")
        pattern = rule.get("pattern")
        message = rule.get("message")
        ignore_case = rule.get("ignore_case", False)
        scan_strings = rule.get("scan_strings", False)
        if (
            not isinstance(rule_id, str)
            or not isinstance(globs, list)
            or not globs
            or not all(isinstance(item, str) and item for item in globs)
            or not isinstance(pattern, str)
            or not pattern
            or not isinstance(message, str)
            or not isinstance(ignore_case, bool)
            or not isinstance(scan_strings, bool)
        ):
            raise RuntimeError("framework source rule is invalid")
        flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
        try:
            expression = re.compile(pattern, flags)
        except re.error as error:
            raise RuntimeError(f"framework source rule regex is invalid: {rule_id}") from error
        candidates: set[Path] = set()
        for glob in globs:
            if Path(glob).is_absolute() or ".." in Path(glob).parts:
                raise RuntimeError(f"framework source rule glob is unsafe: {rule_id}")
            candidates.update(path for path in target.glob(glob) if path.is_file())
        for candidate in sorted(candidates):
            resolved = candidate.resolve()
            if resolved != target and target not in resolved.parents:
                raise RuntimeError(f"framework source rule path escapes target: {rule_id}")
            try:
                source = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError as error:
                raise RuntimeError(f"framework source file is not UTF-8: {candidate}") from error
            inspected = source
            if candidate.suffix == ".py":
                try:
                    tokens = []
                    for token in tokenize.generate_tokens(io.StringIO(source).readline):
                        masked = token.type == tokenize.COMMENT or (
                            token.type == tokenize.STRING and not scan_strings
                        )
                        tokens.append(
                            tokenize.TokenInfo(
                                token.type,
                                "" if masked else token.string,
                                token.start,
                                token.end,
                                token.line,
                            )
                        )
                    inspected = tokenize.untokenize(tokens)
                except (IndentationError, tokenize.TokenError) as error:
                    raise RuntimeError(
                        f"framework source file cannot be tokenized: {candidate}"
                    ) from error
            match = expression.search(inspected)
            if match is None:
                continue
            violations.append(
                {
                    "rule": rule_id,
                    "path": candidate.relative_to(target).as_posix(),
                    "line": inspected.count("\n", 0, match.start()) + 1,
                    "message": message,
                }
            )
    return violations


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
    if not all(isinstance(item, str) for item in required_directories):
        raise RuntimeError("framework required directories are invalid")
    directory_set = set(required_directories)
    missing, wrong_type = _missing_or_wrong_type(target, required, directory_set)
    missing_path_sets = _missing_path_sets(target, contract)
    domain_instances: list[str] = []
    missing_domain_paths: list[str] = []
    wrong_type_domain_paths: list[str] = []
    active_domain_groups: dict[str, list[str]] = {}
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
        active, conditional_missing, conditional_wrong_type = _conditional_domain_paths(
            instance, contract
        )
        active_domain_groups[instance_name] = active
        missing_domain_paths.extend(
            f"{instance_name}/{relative}" for relative in conditional_missing
        )
        wrong_type_domain_paths.extend(
            f"{instance_name}/{relative}" for relative in conditional_wrong_type
        )
    source_violations = _source_violations(target, contract)
    report = {
        "phase": phase,
        "framework": contract.get("framework"),
        "target_root": target_value,
        "required_paths": required,
        "missing_paths": missing,
        "wrong_type_paths": wrong_type,
        "missing_path_sets": missing_path_sets,
        "domain_instances": domain_instances,
        "active_domain_groups": active_domain_groups,
        "missing_domain_paths": missing_domain_paths,
        "wrong_type_domain_paths": wrong_type_domain_paths,
        "source_violations": source_violations,
        "valid": not missing
        and not wrong_type
        and not missing_path_sets
        and not missing_domain_paths
        and not wrong_type_domain_paths
        and not source_violations,
        "checked_at": utc_now(),
    }
    write_json(project / ".ai" / "evidence" / "structure" / f"{phase}.json", report)
    if (
        missing
        or wrong_type
        or missing_path_sets
        or missing_domain_paths
        or wrong_type_domain_paths
        or source_violations
    ):
        raise RuntimeError(
            f"generated {phase} structure is invalid: missing={missing}, wrong_type={wrong_type}, "
            f"missing_sets={missing_path_sets}, domain_missing={missing_domain_paths}, "
            f"domain_wrong_type={wrong_type_domain_paths}, source_violations={source_violations}"
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
    _reject_secret_evidence(evidence, "database verification")
    return evidence


def _reject_secret_evidence(evidence: dict[str, Any], label: str) -> None:
    forbidden_keys = {"database_url", "dsn", "password", "secret", "token"}
    credential_url = re.compile(r"postgres(?:ql)?(?:\+[^:]*)?://[^/@:]+:[^/@]+@", re.I)

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in forbidden_keys:
                    raise RuntimeError(f"{label} evidence contains a secret-bearing key")
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)
        elif isinstance(value, str) and credential_url.search(value):
            raise RuntimeError(f"{label} evidence contains connection credentials")

    inspect(evidence)


def validate_backend_evidence(
    project: Path, schema_path: Path, expected_framework: str
) -> dict[str, Any]:
    evidence = read_json(project / ".ai" / "evidence" / "backend-verification.json")
    schema = read_json(schema_path)
    if not isinstance(evidence, dict) or not isinstance(schema, dict):
        raise RuntimeError("backend verification evidence or schema is missing")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(evidence),
        key=lambda item: list(item.path),
    )
    if errors:
        summaries = [
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise RuntimeError(f"backend verification evidence is invalid: {summaries}")
    if evidence["framework"] != expected_framework:
        raise RuntimeError("backend verification framework does not match the selected backend")
    _reject_secret_evidence(evidence, "backend verification")
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
