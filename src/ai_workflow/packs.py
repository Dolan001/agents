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

    pack_status = []
    for name, relative in catalog.items():
        initialized = _is_initialized(repository, relative)
        pack_status.append(
            {
                "name": name,
                "path": relative,
                "selected": name in reasons,
                "initialized": initialized,
                "reason": reasons.get(name),
                "pinned_commit": _pinned_commit(repository, relative, runner),
            }
        )
    selected = [item for item in pack_status if item["selected"]]
    missing_selected = [item["name"] for item in selected if not item["initialized"]]
    unused_initialized = [
        item["name"] for item in pack_status if item["initialized"] and not item["selected"]
    ]
    manifest: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "workflow_commit": _workflow_commit(repository, runner),
        "prd": {
            "path": prd_path.relative_to(project_root).as_posix(),
            "sha256": hashlib.sha256(prd_path.read_bytes()).hexdigest(),
        },
        "frameworks": dict(frameworks),
        "capabilities": dict(capabilities),
        "deployment_included": include_deployment,
        "selected_packs": selected,
        "missing_selected_packs": missing_selected,
        "unused_initialized_packs": unused_initialized,
        "all_packs": pack_status,
    }
    write_json(project_root / ".ai" / "selected-packs.json", manifest)
    return manifest


def selected_pack_status(project: Path) -> dict[str, Any] | None:
    """Return selection evidence with live initialization and PRD-hash status."""
    project_root = project.resolve()
    payload = read_json(project_root / ".ai" / "selected-packs.json")
    if not isinstance(payload, dict):
        return None
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


def _discover_prd(project: Path, value: str | None) -> Path:
    if value:
        path = Path(value)
        candidate = (path if path.is_absolute() else project / path).resolve()
        choices = [candidate]
    else:
        choices = []
        identities: set[tuple[int, int]] = set()
        for relative in ("docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md"):
            candidate = project / relative
            if not candidate.is_file():
                continue
            metadata = candidate.stat()
            identity = (metadata.st_dev, metadata.st_ino)
            if identity not in identities:
                choices.append(candidate.resolve())
                identities.add(identity)
    if len(choices) != 1:
        raise RuntimeError(
            "provide --prd or keep exactly one PRD at docs/PRD.md, PRD.md, docs/prd.md, or prd.md"
        )
    prd = choices[0]
    if project != prd and project not in prd.parents:
        raise RuntimeError("PRD must be inside the project directory")
    if not prd.is_file() or not prd.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"required PRD is missing or empty: {prd}")
    return prd


def lightweight_main(arguments: list[str] | None = None) -> int:
    """Dependency-free bootstrap CLI used before framework packs are initialized."""
    from .capabilities import detect_prd_capabilities
    from .frameworks import resolve_frameworks

    parser = argparse.ArgumentParser(prog="ai select-packs")
    parser.add_argument("--project", default=".")
    parser.add_argument("--prd")
    parser.add_argument("--frontend", choices=["react", "nextjs", "unknown"], default="unknown")
    parser.add_argument("--mobile", choices=["flutter", "unknown"], default="unknown")
    parser.add_argument(
        "--backend", choices=["django-drf", "fastapi", "unknown"], default="unknown"
    )
    parser.add_argument("--deployment", choices=["aws", "unknown"], default="unknown")
    try:
        args = parser.parse_args(arguments)
        project = Path(args.project).expanduser().resolve()
        if not project.is_dir():
            raise RuntimeError(f"project directory does not exist: {project}")
        prd = _discover_prd(project, args.prd)
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
        print(
            json.dumps(
                {
                    "status": "needs-input" if missing else "ready",
                    "missing_choices": missing,
                    "selection": selection,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:  # noqa: BLE001 - stable bootstrap error boundary
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(lightweight_main())
