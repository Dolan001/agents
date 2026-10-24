"""Start a verified web project on available loopback ports for local review."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from .io import read_json, write_json


def _available_port(preferred: int) -> int:
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", preferred))
        except OSError:
            listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _responds(url: str, *, accept_errors: bool = False) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        return False
    try:
        with urlopen(url, timeout=2) as response:  # noqa: S310 - loopback HTTP only
            return response.status < 500 if accept_errors else response.status < 400
    except HTTPError as error:
        return accept_errors and error.code < 500
    except (OSError, URLError):
        return False


def _compose(project: Path, override: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker is required for local preview")
    return subprocess.run(  # noqa: S603 - fixed Docker argv; no shell
        [
            docker,
            "compose",
            "--project-directory",
            str(project),
            "-f",
            str(project / "compose.yaml"),
            "-f",
            str(override),
            *arguments,
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def _backend_service(port: int, frontend_url: str | None = None) -> dict[str, object]:
    environment = {"DJANGO_ALLOWED_HOSTS": "backend,localhost,127.0.0.1"}
    if frontend_url:
        environment["CSRF_TRUSTED_ORIGINS"] = frontend_url
    return {"ports": [f"127.0.0.1:{port}:8000"], "environment": environment}


def start_backend_preview(project: Path) -> dict[str, object]:
    """Make the verified Compose backend reachable on a live localhost URL."""
    if not (project / "compose.yaml").is_file():
        raise RuntimeError("local backend preview needs compose.yaml with a backend service")
    output = project / ".ai" / "backend-preview.json"
    existing = read_json(output, {})
    if (
        isinstance(existing, dict)
        and isinstance(existing.get("url"), str)
        and isinstance(existing.get("port"), int)
    ):
        if _responds(existing["url"], accept_errors=True):
            return existing
    port = _available_port(8000)
    url = f"http://127.0.0.1:{port}"
    folder = project / ".ai" / "local-preview"
    folder.mkdir(parents=True, exist_ok=True)
    override = folder / "compose.yaml"
    override.write_text(
        json.dumps({"services": {"backend": _backend_service(port)}}, indent=2) + "\n",
        encoding="utf-8",
    )
    result = _compose(project, override, "up", "-d", "--no-build", "backend")
    if result.returncode:
        raise RuntimeError(
            f"local backend Compose startup failed: {(result.stderr or result.stdout)[-1200:]}"
        )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if _responds(url, accept_errors=True):
            evidence: dict[str, object] = {
                "url": url, "port": port,
                "compose_override": str(override.relative_to(project)),
            }
            write_json(output, evidence)
            return evidence
        time.sleep(2)
    logs = _compose(project, override, "logs", "--tail", "30", "backend")
    raise RuntimeError(
        f"local backend did not become ready: {(logs.stdout or logs.stderr)[-1800:]}"
    )


def start_local_preview(project: Path, framework: str) -> dict[str, object]:
    """Start backend and frontend without publishing either beyond localhost."""
    if framework not in {"react", "nextjs"}:
        raise RuntimeError(f"unsupported local web preview framework: {framework}")
    if not (project / "compose.yaml").is_file():
        raise RuntimeError("local preview needs compose.yaml with a backend service")
    frontend = project / "apps" / "frontend"
    package = read_json(frontend / "package.json", {})
    if not isinstance(package, dict) or not package.get("scripts", {}).get("dev"):
        raise RuntimeError("local preview needs apps/frontend/package.json with a dev script")
    if not (frontend / "package-lock.json").is_file():
        raise RuntimeError("local preview needs a committed frontend package-lock.json")

    output = project / ".ai" / "local-preview.json"
    existing = read_json(output, {})
    if isinstance(existing, dict) and all(
        isinstance(existing.get(key), str)
        and _responds(existing[key], accept_errors=key == "backend_url")
        for key in ("url", "backend_url")
    ):
        return existing

    internal_frontend = 3000 if framework == "nextjs" else 5173
    backend_preview = start_backend_preview(project)
    backend_port = int(backend_preview["port"])
    frontend_port = _available_port(internal_frontend)
    while frontend_port == backend_port:
        frontend_port = _available_port(0)
    backend_url = f"http://127.0.0.1:{backend_port}"
    url = f"http://127.0.0.1:{frontend_port}"
    folder = project / ".ai" / "local-preview"
    folder.mkdir(parents=True, exist_ok=True)
    override = folder / "compose.yaml"
    dev_args = "--hostname 0.0.0.0" if framework == "nextjs" else "--host 0.0.0.0"
    # JSON is valid YAML, and prevents paths or commands from becoming shell text.
    services = {
        "backend": _backend_service(backend_port, url),
        "frontend": {
            "image": "node:20.19.5-bookworm-slim",
            "working_dir": "/workspace/apps/frontend",
            "volumes": [
                f"{project}:/workspace",
                "workflow_preview_node_modules:/workspace/apps/frontend/node_modules",
            ],
            "environment": {
                "VITE_API_BASE_URL": backend_url,
                "NEXT_PUBLIC_API_BASE_URL": backend_url,
                "NEXT_PUBLIC_API_URL": backend_url,
                "VITE_REALTIME_WS_URL": f"ws://127.0.0.1:{backend_port}",
                "NEXT_PUBLIC_REALTIME_WS_URL": f"ws://127.0.0.1:{backend_port}",
            },
            "command": [
                "sh",
                "-ec",
                "test -f node_modules/.package-lock.json || "
                "npm ci --no-audit --no-fund; "
                f"npm run dev -- {dev_args} --port {internal_frontend}",
            ],
            "ports": [f"127.0.0.1:{frontend_port}:{internal_frontend}"],
            "depends_on": {"backend": {"condition": "service_started"}},
        },
    }
    override.write_text(
        json.dumps(
            {"services": services, "volumes": {"workflow_preview_node_modules": {}}}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    result = _compose(project, override, "up", "-d", "--no-build", "backend", "frontend")
    if result.returncode:
        raise RuntimeError(
            f"local preview Compose startup failed: {(result.stderr or result.stdout)[-1200:]}"
        )
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if _responds(url) and _responds(backend_url, accept_errors=True):
            evidence: dict[str, object] = {
                "url": url,
                "backend_url": backend_url,
                "frontend_port": frontend_port,
                "backend_port": backend_port,
                "framework": framework,
                "compose_override": str(override.relative_to(project)),
            }
            write_json(output, evidence)
            return evidence
        time.sleep(2)
    logs = _compose(project, override, "logs", "--tail", "30", "backend", "frontend")
    raise RuntimeError(
        f"local preview did not become ready: {(logs.stdout or logs.stderr)[-1800:]}"
    )
