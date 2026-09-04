"""Select and lazily initialize only PRD-required behavior-pack submodules."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .model import utc_now
from .pipeline import workflow_root

GitRunner = Callable[[Path, list[str]], tuple[int, str]]

FRAMEWORK_PACKS = {
    "react": "reactjs",
    "nextjs": "nextjs",
    "flutter": "flutter",
    "django-drf": "drf",
    "fastapi": "fastapi",
}
CAPABILITY_PACKS = {"rag": "rag", "webscraping": "webscraping"}
MANIFEST_VERSION = 2


def _run_git(directory: Path, arguments: list[str]) -> tuple[int, str]:
    executable = shutil.which("git")
    if executable is None:
        return 127, "git executable is unavailable"
    result = subprocess.run(  # noqa: S603 - arguments are fixed or repository-owned paths
        [executable, *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return result.returncode, output


def select_pack_names(
    frameworks: dict[str, str],
    capabilities: dict[str, bool],
    *,
    include_deployment: bool = False,
) -> dict[str, str]:
    """Return ordered pack names and requirement-backed selection reasons."""
    selected = {"base": "required shared workflow behavior"}
    for side in ("frontend", "mobile", "backend"):
        framework = frameworks.get(side, "unknown")
        pack = FRAMEWORK_PACKS.get(framework)
        if pack:
            selected[pack] = f"{side} framework: {framework}"
    for capability, pack in CAPABILITY_PACKS.items():
        if capabilities.get(capability) is True:
            selected[pack] = f"PRD capability: {capability}"
    if include_deployment and frameworks.get("deployment") == "aws":
        selected["aws"] = "explicit AWS deployment workflow"
    return selected


def missing_framework_choices(frameworks: dict[str, str]) -> list[str]:
    """Report choices that block a complete application build."""
    missing: list[str] = []
    if frameworks.get("frontend") == "unknown" and frameworks.get("mobile") == "unknown":
        missing.append("client: react, nextjs, or flutter")
    if frameworks.get("backend") == "unknown":
        missing.append("backend: django-drf or fastapi")
    return missing


def _catalog(root: Path) -> dict[str, str]:
    config = read_json(root / "config" / "framework-packs.json")
    if not isinstance(config, dict):
        raise RuntimeError("framework pack catalog is missing")
    catalog = {"base": "base", "aws": "aws"}
    for section in ("packs", "capability_packs"):
        entries = config.get(section)
        if not isinstance(entries, dict):
            raise RuntimeError(f"framework pack catalog section is missing: {section}")
        for specification in entries.values():
            if not isinstance(specification, dict) or not isinstance(
                specification.get("path"), str
            ):
                raise RuntimeError(f"invalid framework pack catalog section: {section}")
            path = specification["path"]
            candidate = (root / path).resolve()
            if Path(path).is_absolute() or candidate == root or root not in candidate.parents:
                raise RuntimeError(f"behavior pack path escapes workflow repository: {path}")
            catalog[path] = path
    return catalog


def _is_initialized(root: Path, relative: str) -> bool:
    pack = root / relative
    return (pack / ".git").exists() and (pack / "AGENTS.md").is_file()


def _validate_pack_contract(root: Path, name: str, relative: str) -> None:
    required = ["AGENTS.md", "agents/catalog.json", "skills/catalog.json", "hooks/lifecycle.json"]
    if name != "base":
        required.append("rules/project-structure.json")
    missing = [path for path in required if not (root / relative / path).is_file()]
    if missing:
        raise RuntimeError(
            f"selected behavior pack is incomplete ({name}): {', '.join(missing)}"
        )


def _pinned_commit(root: Path, relative: str, runner: GitRunner) -> str | None:
    code, output = runner(root, ["ls-files", "--stage", "--", relative])
    if code != 0 or not output:
        return None
    fields = output.split(maxsplit=3)
    return fields[1] if len(fields) >= 3 and fields[0] == "160000" else None


def _workflow_commit(root: Path, runner: GitRunner) -> str | None:
    code, output = runner(root, ["rev-parse", "HEAD"])
    return output.splitlines()[0] if code == 0 and output else None


def _validate_manifest(payload: Any, repository: Path | None = None) -> dict[str, Any]:
    """Validate the selection manifest without requiring bootstrap dependencies."""
    if not isinstance(payload, dict):
        raise RuntimeError("selected-pack manifest must be a JSON object")
    required = {
        "version": int,
        "status": str,
        "generated_at": str,
        "source": dict,
        "frameworks": dict,
        "capabilities": dict,
        "deployment_included": bool,
        "selected_packs": list,
        "missing_selected_packs": list,
        "unused_initialized_packs": list,
        "all_packs": list,
    }
    for field, expected in required.items():
        if not isinstance(payload.get(field), expected):
            raise RuntimeError(f"invalid selected-pack manifest field: {field}")
    if payload["version"] != MANIFEST_VERSION:
        raise RuntimeError(f"unsupported selected-pack manifest version: {payload['version']}")
    if "prd" not in payload:
        raise RuntimeError("invalid selected-pack manifest field: prd")
    if payload.get("workflow_commit") is not None and not isinstance(
        payload.get("workflow_commit"), str
    ):
        raise RuntimeError("invalid selected-pack manifest field: workflow_commit")
    if payload["status"] not in {"awaiting-prd", "ready"}:
        raise RuntimeError("invalid selected-pack manifest status")
    source = payload["source"]
    if source.get("kind") not in {"requirements", "prd"}:
        raise RuntimeError("invalid selected-pack manifest source kind")
    if not all(
        isinstance(source.get(field), str) and source[field] for field in ("path", "sha256")
    ):
        raise RuntimeError("selected-pack manifest source requires path and sha256")
    prd = payload.get("prd")
    if prd is not None and not (
        isinstance(prd, dict)
        and isinstance(prd.get("path"), str)
        and isinstance(prd.get("sha256"), str)
    ):
        raise RuntimeError("invalid selected-pack manifest PRD evidence")
    if payload["status"] == "ready" and prd is None:
        raise RuntimeError("ready selected-pack manifest requires PRD evidence")
    pack_fields = {
        "name": str,
        "path": str,
        "selected": bool,
        "initialized": bool,
    }
    for pack in payload["all_packs"]:
        if not isinstance(pack, dict) or any(
            not isinstance(pack.get(field), expected) for field, expected in pack_fields.items()
        ):
            raise RuntimeError("invalid selected-pack manifest pack entry")
        if pack.get("reason") is not None and not isinstance(pack.get("reason"), str):
            raise RuntimeError("invalid selected-pack manifest pack reason")
        if pack.get("pinned_commit") is not None and not isinstance(
            pack.get("pinned_commit"), str
        ):
            raise RuntimeError("invalid selected-pack manifest pinned commit")
    schema = (repository or workflow_root()) / "schemas" / "selected-packs.schema.json"
    if schema.is_file():
        try:
            from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
        except ModuleNotFoundError:
            pass
        else:
            errors = sorted(
                Draft202012Validator(read_json(schema)).iter_errors(payload),
                key=lambda error: list(error.absolute_path),
            )
            if errors:
                location = ".".join(str(part) for part in errors[0].absolute_path) or "root"
                raise RuntimeError(
                    f"selected-pack manifest schema violation at {location}: "
                    f"{errors[0].message}"
                )
    return payload


def _pack_status(
    repository: Path,
    catalog: dict[str, str],
    reasons: dict[str, str],
    *,
    initialize: bool,
    runner: GitRunner,
) -> list[dict[str, Any]]:
    unknown = sorted(set(reasons) - set(catalog))
    if unknown:
        raise RuntimeError(f"selected packs are absent from the catalog: {', '.join(unknown)}")
    missing = [name for name in reasons if not _is_initialized(repository, catalog[name])]
    if initialize and missing:
        paths = [catalog[name] for name in missing]
        code, output = runner(repository, ["submodule", "update", "--init", "--", *paths])
        if code != 0:
            raise RuntimeError(
                "required behavior-pack initialization failed "
                f"({', '.join(missing)}): {output or 'git returned no diagnostic'}"
            )
        still_missing = [name for name in missing if not _is_initialized(repository, catalog[name])]
        if still_missing:
            raise RuntimeError(
                "required behavior packs remain unavailable after initialization: "
                f"{', '.join(still_missing)}"
            )
    for name in reasons:
        if _is_initialized(repository, catalog[name]):
            _validate_pack_contract(repository, name, catalog[name])
    return [
        {
            "name": name,
            "path": relative,
            "selected": name in reasons,
            "initialized": _is_initialized(repository, relative),
            "reason": reasons.get(name),
            "pinned_commit": _pinned_commit(repository, relative, runner),
        }
        for name, relative in catalog.items()
    ]


def _manifest(
    project: Path,
    repository: Path,
    source: Path,
    source_kind: str,
    frameworks: dict[str, str],
    capabilities: dict[str, bool],
    include_deployment: bool,
    pack_status: list[dict[str, Any]],
    runner: GitRunner,
) -> dict[str, Any]:
    source_evidence = {
        "path": source.relative_to(project).as_posix(),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    selected = [item for item in pack_status if item["selected"]]
    payload: dict[str, Any] = {
        "version": MANIFEST_VERSION,
        "status": "ready" if source_kind == "prd" else "awaiting-prd",
        "generated_at": utc_now(),
        "workflow_commit": _workflow_commit(repository, runner),
        "source": {"kind": source_kind, **source_evidence},
        "prd": source_evidence if source_kind == "prd" else None,
        "frameworks": dict(frameworks),
        "capabilities": dict(capabilities),
        "deployment_included": include_deployment,
        "selected_packs": selected,
        "missing_selected_packs": [
            item["name"] for item in selected if not item["initialized"]
        ],
        "unused_initialized_packs": [
            item["name"]
            for item in pack_status
            if item["initialized"] and not item["selected"]
        ],
        "all_packs": pack_status,
    }
    _validate_manifest(payload, repository)
    write_json(project / ".ai" / "selected-packs.json", payload)
    return payload


def reconcile_selected_packs(
    project: Path,
    prd: Path,
    frameworks: dict[str, str],
    capabilities: dict[str, bool],
    *,
    include_deployment: bool = False,
    initialize: bool = True,
    root: Path | None = None,
    runner: GitRunner = _run_git,
) -> dict[str, Any]:
    """Initialize required packs and persist exact selection evidence."""
    project_root = project.resolve()
    repository = (root or workflow_root()).resolve()
    prd_path = prd.resolve()
    if prd_path != project_root and project_root not in prd_path.parents:
        raise RuntimeError("PRD must be inside the project directory")

    catalog = _catalog(repository)
    reasons = select_pack_names(
        frameworks, capabilities, include_deployment=include_deployment
    )
    pack_status = _pack_status(
        repository, catalog, reasons, initialize=initialize, runner=runner
    )
    return _manifest(
        project_root,
        repository,
        prd_path,
        "prd",
        frameworks,
        capabilities,
        include_deployment,
        pack_status,
        runner,
    )


def bootstrap_base_pack(
    project: Path,
    requirements: Path,
    *,
    initialize: bool = True,
    root: Path | None = None,
    runner: GitRunner = _run_git,
) -> dict[str, Any]:
    """Initialize only base so a requirements-only project can generate its PRD."""
    project_root = project.resolve()
    repository = (root or workflow_root()).resolve()
    source = requirements.resolve()
    if source != project_root and project_root not in source.parents:
        raise RuntimeError("requirements must be inside the project directory")
    if not source.is_file() or not source.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"required requirements file is missing or empty: {source}")
    status = _pack_status(
        repository,
        _catalog(repository),
        {"base": "required to generate a build-ready PRD"},
        initialize=initialize,
        runner=runner,
    )
    frameworks = {
        "frontend": "unknown",
        "mobile": "unknown",
        "backend": "unknown",
        "deployment": "unknown",
    }
    return _manifest(
        project_root,
        repository,
        source,
        "requirements",
        frameworks,
        {"rag": False, "webscraping": False},
        False,
        status,
        runner,
    )


def selected_pack_status(project: Path) -> dict[str, Any] | None:
    """Return selection evidence with live initialization and PRD-hash status."""
    project_root = project.resolve()
    raw = read_json(project_root / ".ai" / "selected-packs.json")
    if raw is None:
        return None
    payload = _validate_manifest(raw, workflow_root())
    packs = payload.get("all_packs")
    if isinstance(packs, list):
        for item in packs:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                item["initialized"] = _is_initialized(workflow_root(), item["path"])
        payload["selected_packs"] = [
            item for item in packs if isinstance(item, dict) and item.get("selected") is True
        ]
        payload["missing_selected_packs"] = [
            item["name"]
            for item in payload["selected_packs"]
            if item.get("initialized") is not True
        ]
        payload["unused_initialized_packs"] = [
            item["name"]
            for item in packs
            if isinstance(item, dict)
            and item.get("selected") is not True
            and item.get("initialized") is True
        ]
    prd = payload.get("prd")
    if isinstance(prd, dict) and isinstance(prd.get("path"), str):
        path = (project_root / prd["path"]).resolve()
        recorded_hash = prd.get("sha256")
        payload["prd_hash_current"] = (
            path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == recorded_hash
        )
    return payload


def _discover_input(
    project: Path, value: str | None, candidates: tuple[str, ...], label: str
) -> Path | None:
    if value:
        path = Path(value)
        candidate = (path if path.is_absolute() else project / path).resolve()
        choices = [candidate]
    else:
        choices = []
        identities: set[tuple[int, int]] = set()
        for relative in candidates:
            candidate = project / relative
            if not candidate.is_file():
                continue
            metadata = candidate.stat()
            identity = (metadata.st_dev, metadata.st_ino)
            if identity not in identities:
                choices.append(candidate.resolve())
                identities.add(identity)
    if not choices and not value:
        return None
    if len(choices) != 1:
        locations = ", ".join(candidates)
        raise RuntimeError(f"provide --{label} or keep exactly one {label} at {locations}")
    selected = choices[0]
    if project != selected and project not in selected.parents:
        raise RuntimeError(f"{label} must be inside the project directory")
    if not selected.is_file() or not selected.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"required {label} is missing or empty: {selected}")
    return selected


def discover_pack_prd(project: Path, value: str | None) -> Path | None:
    return _discover_input(
        project, value, ("docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md"), "prd"
    )


def discover_pack_requirements(project: Path, value: str | None) -> Path | None:
    return _discover_input(
        project,
        value,
        ("docs/REQUIREMENTS.md", "REQUIREMENTS.md", "docs/requirements.md", "requirements.md"),
        "requirements",
    )


def add_pack_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".")
    parser.add_argument("--prd")
    parser.add_argument("--requirements")
    parser.add_argument("--frontend", choices=["react", "nextjs", "unknown"], default="unknown")
    parser.add_argument("--mobile", choices=["flutter", "unknown"], default="unknown")
    parser.add_argument(
        "--backend", choices=["django-drf", "fastapi", "unknown"], default="unknown"
    )
    parser.add_argument("--deployment", choices=["aws", "unknown"], default="unknown")


def select_from_inputs(args: argparse.Namespace) -> dict[str, Any]:
    """Apply the shared PRD-or-requirements selection behavior for both CLIs."""
    from .capabilities import detect_prd_capabilities
    from .frameworks import resolve_frameworks

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise RuntimeError(f"project directory does not exist: {project}")
    prd = discover_pack_prd(project, args.prd)
    if prd is None:
        requirements = discover_pack_requirements(project, args.requirements)
        if requirements is None:
            raise RuntimeError(
                "no PRD or requirements found; provide --prd or --requirements"
            )
        selection = bootstrap_base_pack(project, requirements)
        return {
            "status": "needs-prd",
            "missing_choices": [],
            "next": f"$generate-prd --requirements {requirements.relative_to(project).as_posix()}",
            "selection": selection,
        }
    deployment_requested = args.deployment == "aws"
    frameworks = resolve_frameworks(
        prd, args.frontend, args.mobile, args.backend, args.deployment
    )
    selection = reconcile_selected_packs(
        project,
        prd,
        frameworks,
        detect_prd_capabilities(prd),
        include_deployment=deployment_requested,
    )
    missing = missing_framework_choices(frameworks)
    return {
        "status": "needs-input" if missing else "ready",
        "missing_choices": missing,
        "selection": selection,
    }


def build_lightweight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai select-packs")
    add_pack_selection_arguments(parser)
    return parser


def lightweight_main(arguments: list[str] | None = None) -> int:
    """Dependency-free bootstrap CLI used before framework packs are initialized."""
    parser = build_lightweight_parser()
    try:
        args = parser.parse_args(arguments)
        print(json.dumps(select_from_inputs(args), indent=2, sort_keys=True))
        return 0
    except Exception as error:  # noqa: BLE001 - stable bootstrap error boundary
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(lightweight_main())
