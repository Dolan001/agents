"""Run allow-listed, project-owned commands without a shell."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .io import append_jsonl, read_json, write_json
from .model import utc_now

_SECRET_ENVIRONMENT_KEYS = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "CLOUDFLARE_API_TOKEN",
}
_IGNORED_CACHE_DIRS = {
    ".agents",
    ".ai",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "artifacts",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "__pycache__",
}


def _static_cache_key(
    project: Path,
    specification: dict[str, Any],
    executable: str,
    environment: Mapping[str, str],
) -> str | None:
    """Opt-in reuse for read-only checks with declared, existing source inputs."""
    cache = specification.get("cache")
    if cache is None:
        return None
    if (
        not isinstance(cache, dict)
        or cache.get("mode") != "static"
        or cache.get("read_only") is not True
        or not isinstance(cache.get("inputs"), list)
        or not cache["inputs"]
    ):
        raise RuntimeError("static check cache requires read_only:true and declared inputs")
    if specification["argv"][0] in {"docker", "make"}:
        raise RuntimeError("Docker and Make commands cannot use the static check cache")
    digest = hashlib.sha256(b"static-check-v1\0")
    digest.update(
        json.dumps(
            {
                "argv": specification["argv"],
                "cwd": specification.get("cwd", "."),
                "python": sys.version,
                "executable": str(Path(executable).resolve()),
                # Hash every inherited variable so an undeclared environment change cannot
                # silently reuse a result. The values are never written to evidence.
                "environment": dict(environment),
            },
            sort_keys=True,
        ).encode()
    )
    executable_stat = Path(executable).stat()
    digest.update(f"{executable_stat.st_size}:{executable_stat.st_mtime_ns}".encode())
    # Conservative whole-source fingerprint. Explicit inputs cover generated
    # evidence when a read-only command depends on it.
    for directory, names, files in os.walk(project):
        names[:] = sorted(name for name in names if name not in _IGNORED_CACHE_DIRS)
        for name in sorted(files):
            path = Path(directory) / name
            resolved = path.resolve()
            if project not in resolved.parents or not resolved.is_file():
                continue
            digest.update(path.relative_to(project).as_posix().encode())
            digest.update(hashlib.sha256(resolved.read_bytes()).digest())
    for pattern in sorted(set(cache["inputs"])):
        candidate = (project / pattern).resolve()
        if candidate != project and project not in candidate.parents:
            raise RuntimeError(f"static cache input escapes project: {pattern}")
        paths = [path for path in project.glob(pattern) if path.is_file()]
        if not paths:
            raise RuntimeError(f"static cache input has no files: {pattern}")
        for path in sorted(paths):
            resolved = path.resolve()
            if project not in resolved.parents:
                raise RuntimeError(f"static cache input escapes project: {path}")
            digest.update(path.relative_to(project).as_posix().encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _redact_output(value: str, environment: Mapping[str, str]) -> str:
    redacted = value
    for key in _SECRET_ENVIRONMENT_KEYS:
        secret = environment.get(key, "")
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _failure_kind(returncode: int, output: str) -> str:
    if returncode == 0:
        return "passed"
    lowered = output.lower()
    if "modulenotfounderror" in lowered or "no module named" in lowered:
        return "missing_dependency"
    if any(
        marker in lowered
        for marker in (
            "no space left on device",
            "docker daemon",
            "command not found",
        )
    ):
        return "environment_blocker"
    return "unclassified_failure"


def run_command_groups(
    project: Path,
    groups: list[str],
    environment: Mapping[str, str] | None = None,
    *,
    require_fresh: bool = False,
) -> dict[str, Any]:
    manifest = read_json(project / ".ai" / "test-commands.json")
    if not isinstance(manifest, dict):
        raise RuntimeError(".ai/test-commands.json is required for deterministic execution")
    configured = manifest.get("commands")
    if not isinstance(configured, dict):
        raise RuntimeError("test command manifest must contain a commands object")
    results: list[dict[str, Any]] = []
    cache_path = project / ".ai" / "cache" / "static-checks.json"
    cache_state = read_json(cache_path, {})
    if not isinstance(cache_state, dict):
        cache_state = {}
    command_environment = os.environ.copy()
    if environment:
        command_environment.update(environment)
    planned: list[tuple[str, int, Any, list[str], str, Path, str]] = []
    for group in groups:
        commands = configured.get(group)
        if not isinstance(commands, list) or not commands:
            raise RuntimeError(f"no approved commands configured for group: {group}")
        for index, specification in enumerate(commands):
            argv = specification.get("argv") if isinstance(specification, dict) else specification
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise RuntimeError(f"invalid argv for {group}[{index}]")
            relative_cwd = specification.get("cwd", ".") if isinstance(specification, dict) else "."
            cwd = (project / relative_cwd).resolve()
            if cwd != project and project not in cwd.parents:
                raise RuntimeError(f"command cwd escapes project: {relative_cwd}")
            local_executable = (cwd / argv[0]).resolve()
            if Path(argv[0]).is_absolute():
                executable = shutil.which(argv[0])
            elif "/" in argv[0]:
                if local_executable != project and project not in local_executable.parents:
                    raise RuntimeError(f"command executable escapes project: {argv[0]}")
                executable = str(local_executable) if local_executable.is_file() else None
            else:
                executable = shutil.which(argv[0])
            if not executable:
                raise RuntimeError(f"command executable unavailable: {argv[0]}")
            planned.append((group, index, specification, argv, relative_cwd, cwd, executable))

    # Resolve every executable before spending time on the first command. A late
    # missing tool must not cause an otherwise avoidable partial test matrix.
    def execute_one(
        item: tuple[str, int, Any, list[str], str, Path, str],
    ) -> dict[str, Any]:
        group, index, specification, argv, relative_cwd, cwd, executable = item
        key = (
            _static_cache_key(project, specification, executable, command_environment)
            if isinstance(specification, dict) and not require_fresh
            else None
        )
        cached = cache_state.get(key) if key else None
        if isinstance(cached, dict) and cached.get("passed") is True:
            return {
                "group": group,
                "index": index,
                "argv": argv,
                "cwd": relative_cwd,
                "returncode": 0,
                "stdout_tail": "",
                "stderr_tail": "",
                "elapsed_ms": 0,
                "cached": True,
                "cache_key": key,
                "failure_kind": "passed",
            }
        timeout = (
            specification.get("timeout_seconds", 1200) if isinstance(specification, dict) else 1200
        )
        started = time.monotonic()
        completed = subprocess.run(  # noqa: S603 - argv only; no shell; confined cwd
            [executable, *argv[1:]],
            cwd=cwd,
            text=True,
            capture_output=True,
            env=command_environment,
            timeout=int(timeout),
            check=False,
        )
        result = {
            "group": group,
            "index": index,
            "argv": argv,
            "cwd": relative_cwd,
            "returncode": completed.returncode,
            "stdout_tail": _redact_output(completed.stdout[-4000:], command_environment),
            "stderr_tail": _redact_output(completed.stderr[-4000:], command_environment),
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "cached": False,
            "failure_kind": _failure_kind(
                completed.returncode, completed.stdout[-4000:] + completed.stderr[-4000:]
            ),
        }
        if key:
            result["cache_key"] = key
        return result

    def record(result: dict[str, Any]) -> None:
        results.append(result)
        append_jsonl(
            project / ".ai/telemetry/commands.jsonl",
            {
                "at": utc_now(),
                "group": result["group"],
                "index": result["index"],
                "elapsed_ms": result["elapsed_ms"],
                "cached": result["cached"],
                "returncode": result["returncode"],
            },
        )
        key = result.get("cache_key")
        if key and result["returncode"] == 0 and not result["cached"]:
            cache_state[key] = {"passed": True, "executed_at": utc_now()}
            while len(cache_state) > 200:
                cache_state.pop(next(iter(cache_state)))
            write_json(cache_path, cache_state)

    position = 0
    while position < len(planned):
        group = planned[position][0]
        end = position + 1
        while end < len(planned) and planned[end][0] == group:
            end += 1
        batch = planned[position:end]
        parallel = not require_fresh and len(batch) > 1 and all(
            isinstance(item[2], dict)
            and item[2].get("parallel_safe") is True
            and isinstance(item[2].get("cache"), dict)
            and item[2]["cache"].get("mode") == "static"
            and item[2]["cache"].get("read_only") is True
            for item in batch
        )
        if parallel:
            with ThreadPoolExecutor(max_workers=min(2, len(batch))) as pool:
                batch_results = list(pool.map(execute_one, batch))
        else:
            batch_results = []
            for item in batch:
                result = execute_one(item)
                batch_results.append(result)
                if result["returncode"] != 0:
                    break
        for result in batch_results:
            record(result)
        failed = next((result for result in batch_results if result["returncode"] != 0), None)
        if failed is not None:
            report = {"passed": False, "executed_at": utc_now(), "results": results}
            write_json(project / "artifacts" / "tests" / "command-results.json", report)
            raise RuntimeError(f"approved command failed: {failed['group']}[{failed['index']}]")
        position = end
    report = {"passed": True, "executed_at": utc_now(), "results": results}
    write_json(project / "artifacts" / "tests" / "command-results.json", report)
    return report
