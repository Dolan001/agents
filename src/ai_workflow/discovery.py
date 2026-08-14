"""Deterministic, read-only repository discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .git import baseline
from .io import write_json
from .model import utc_now

IGNORED = {".git", ".next", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def project_files(project: Path, maximum: int = 5000) -> list[str]:
    files: list[str] = []
    for candidate in project.rglob("*"):
        if any(part in IGNORED for part in candidate.relative_to(project).parts):
            continue
        if candidate.is_file():
            files.append(candidate.relative_to(project).as_posix())
            if len(files) >= maximum:
                break
    return sorted(files)


def detect(files: list[str]) -> dict[str, Any]:
    file_set = set(files)
    frontend = "unknown"
    mobile = "unknown"
    backend = "unknown"
    reasons: list[str] = []
    package_files = [name for name in files if name.endswith("package.json")]
    for package_file in package_files:
        reasons.append(f"JavaScript manifest: {package_file}")
    if any(
        name.endswith(("next.config.js", "next.config.mjs", "next.config.ts")) for name in files
    ):
        frontend = "nextjs"
    elif package_files:
        frontend = "react"
    if "apps/mobile/pubspec.yaml" in file_set or (
        "pubspec.yaml" in file_set and any(name.startswith("lib/") for name in files)
    ):
        mobile = "flutter"
        reasons.append("Flutter pubspec.yaml detected")
    if "manage.py" in file_set or any(name.endswith("/manage.py") for name in files):
        backend = "django-drf"
        reasons.append("Django manage.py detected")
    elif any(name.endswith("/app/main.py") or name == "app/main.py" for name in files):
        backend = "fastapi"
        reasons.append("FastAPI app/main.py shape detected")
    return {"frontend": frontend, "mobile": mobile, "backend": backend, "reasons": reasons}


def inventory(project: Path) -> dict[str, Any]:
    files = project_files(project)
    frameworks = detect(files)
    routes = [
        name
        for name in files
        if name.endswith(("urls.py", "page.tsx", "route.ts", "routes.ts", "router.ts"))
    ]
    tests = [
        name
        for name in files
        if "/test" in name
        or name.startswith("test")
        or name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    ]
    migrations = [name for name in files if "/migrations/" in name]
    environments = [name for name in files if Path(name).name.startswith(".env")]
    ci = [name for name in files if name.startswith(".github/workflows/")]
    designs = [
        name
        for name in files
        if name.lower().endswith((".html", ".png", ".jpg", ".jpeg", ".webp", ".fig", ".svg"))
    ]
    return {
        "generated_at": utc_now(),
        "repository_map": {"files": files, "truncated": len(files) >= 5000},
        "framework_detection": frameworks,
        "frontend_route_map": routes,
        "test_inventory": tests,
        "migration_state": migrations,
        "environment_inventory": environments,
        "ci_inventory": ci,
        "design_inventory": designs,
        "git_baseline": baseline(project),
        "risks": discover_risks(files),
    }


def discover_risks(files: list[str]) -> list[dict[str, str]]:
    risks = []
    if not any(name.startswith(".github/workflows/") for name in files):
        risks.append({"code": "NO_CI", "severity": "medium", "message": "No CI workflow detected."})
    if not any(Path(name).name == ".env.example" for name in files):
        risks.append(
            {"code": "NO_ENV_EXAMPLE", "severity": "medium", "message": "No .env.example detected."}
        )
    if not any("test" in name.lower() for name in files):
        risks.append({"code": "NO_TESTS", "severity": "high", "message": "No tests detected."})
    return risks


def save_inventory(project: Path, report: dict[str, Any]) -> None:
    destination = project / ".ai" / "discovery"
    mapping = {
        "repository-map.json": report["repository_map"],
        "framework-detection.json": report["framework_detection"],
        "frontend-route-map.json": {"routes": report["frontend_route_map"]},
        "test-inventory.json": {"tests": report["test_inventory"]},
        "migration-state.json": {"migrations": report["migration_state"]},
        "environment-inventory.json": {"files": report["environment_inventory"]},
        "ci-inventory.json": {"files": report["ci_inventory"]},
        "design-inventory.json": {"files": report["design_inventory"]},
        "git-baseline.json": report["git_baseline"],
        "risks.json": {"risks": report["risks"]},
        "api-inventory.json": {"routes": report["frontend_route_map"]},
        "django-app-map.json": {"apps": []},
        "fastapi-module-map.json": {"modules": []},
        "component-map.json": {"components": []},
    }
    for name, payload in mapping.items():
        write_json(destination / name, payload)


def print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
