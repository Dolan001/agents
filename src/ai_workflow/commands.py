"""Run allow-listed, project-owned commands without a shell."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .model import utc_now


def run_command_groups(project: Path, groups: list[str]) -> dict[str, Any]:
    manifest = read_json(project / ".ai" / "test-commands.json")
    if not isinstance(manifest, dict):
        raise RuntimeError(".ai/test-commands.json is required for deterministic execution")
    configured = manifest.get("commands")
    if not isinstance(configured, dict):
        raise RuntimeError("test command manifest must contain a commands object")
    results: list[dict[str, Any]] = []
    for group in groups:
        commands = configured.get(group)
        if not isinstance(commands, list) or not commands:
            raise RuntimeError(f"no approved commands configured for group: {group}")
        for index, specification in enumerate(commands):
            argv = specification.get("argv") if isinstance(specification, dict) else specification
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise RuntimeError(f"invalid argv for {group}[{index}]")
            executable = shutil.which(argv[0])
            if not executable:
                raise RuntimeError(f"command executable unavailable: {argv[0]}")
            relative_cwd = specification.get("cwd", ".") if isinstance(specification, dict) else "."
            cwd = (project / relative_cwd).resolve()
            if cwd != project and project not in cwd.parents:
                raise RuntimeError(f"command cwd escapes project: {relative_cwd}")
            timeout = (
                specification.get("timeout_seconds", 1200)
                if isinstance(specification, dict)
                else 1200
            )
            completed = subprocess.run(  # noqa: S603 - argv only; no shell; confined cwd
                [executable, *argv[1:]],
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=int(timeout),
                check=False,
            )
            result = {
                "group": group,
                "index": index,
                "argv": argv,
                "cwd": relative_cwd,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
            results.append(result)
            if completed.returncode != 0:
                report = {"passed": False, "executed_at": utc_now(), "results": results}
                write_json(project / "artifacts" / "tests" / "command-results.json", report)
                raise RuntimeError(f"approved command failed: {group}[{index}]")
    report = {"passed": True, "executed_at": utc_now(), "results": results}
    write_json(project / "artifacts" / "tests" / "command-results.json", report)
    return report
