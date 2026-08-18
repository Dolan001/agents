"""Production-safe command-line interface."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from .commands import run_command_groups
from .deployment import deployment_status, execute_operation
from .design import classify_design_inputs, ingest_design_inputs
from .design_fidelity import sync_design
from .discovery import inventory, print_json, save_inventory
from .execution import evaluate_phase_gate, execute_phase
from .frameworks import resolve_frameworks
from .git import assert_safe_branch, baseline, prepare_feature_branch, run_git
from .io import append_jsonl, read_json, write_json
from .model import PHASES, StateStore, utc_now
from .pipeline import ready_phases, validate_control_plane
from .prd import generate_prd
from .requirements import parse_prd, save_requirement_outputs
from .requirements import reconcile as reconcile_requirements
from .tokens import resolve_token
from .visual_diff import compare_pixels, parse_mask

Command = Callable[[argparse.Namespace], int]


def project_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def resolved_project(value: str) -> Path:
    project = Path(value).expanduser().resolve()
    if not project.exists() or not project.is_dir():
        raise RuntimeError(f"project directory does not exist: {project}")
    return project


def require_prd(project: Path, value: str) -> Path:
    candidate = Path(value)
    path = candidate if candidate.is_absolute() else project / candidate
    path = path.resolve()
    if project not in path.parents and path != project:
        raise RuntimeError("PRD must be inside the project directory")
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise RuntimeError(f"required PRD is missing or empty: {path}")
    return path


def discover_prd(project: Path, value: str | None) -> Path:
    if value:
        return require_prd(project, value)
    candidates: list[Path] = []
    identities: set[tuple[int, int]] = set()
    for relative in ("docs/PRD.md", "PRD.md", "docs/prd.md", "prd.md"):
        candidate = project / relative
        if not candidate.is_file():
            continue
        metadata = candidate.stat()
        identity = (metadata.st_dev, metadata.st_ino)
        if identity not in identities:
            candidates.append(candidate.resolve())
            identities.add(identity)
    if len(candidates) != 1:
        raise RuntimeError(
            "provide --prd or keep exactly one PRD at docs/PRD.md, PRD.md, docs/prd.md, or prd.md"
        )
    return require_prd(project, str(candidates[0]))


def initialize(args: argparse.Namespace, mode: str) -> int:
    project = resolved_project(args.project)
    prd = require_prd(project, args.prd)
    ingested_design = ingest_design_inputs(
        project,
        getattr(args, "html", None),
        getattr(args, "screenshot", None),
    )
    github_user = getattr(args, "github_user", None)
    if github_user:
        prepare_feature_branch(
            project,
            github_user,
            getattr(args, "branch_feature", None) or project.name,
        )
    git = baseline(project)
    branch = git["branch"] if isinstance(git["branch"], str) else None
    if branch:
        assert_safe_branch(branch)
    frameworks = {
        "frontend": args.frontend,
        "mobile": getattr(args, "mobile", "unknown"),
        "backend": args.backend,
        "deployment": getattr(args, "deployment", "unknown"),
    }
    if mode == "brownfield":
        report = inventory(project)
        detected = report["framework_detection"]
        for side in ("frontend", "mobile", "backend"):
            if frameworks[side] == "unknown":
                frameworks[side] = detected[side]
    state = StateStore(project).create(
        project_id=project_slug(args.project_id or project.name),
        mode=mode,
        frontend=frameworks["frontend"],
        backend=frameworks["backend"],
        baseline=git["baseline_commit"] if isinstance(git["baseline_commit"], str) else None,
        branch=branch,
        assumptions=[
            f"PRD source: {prd.relative_to(project)}",
            "Local work is allowed; remote push requires explicit configuration.",
        ],
        mobile=frameworks["mobile"],
        deployment=frameworks["deployment"],
    )
    save_inventory(project, inventory(project))
    design_inputs = classify_design_inputs(project)
    state["completed_phases"] = ["bootstrap"]
    StateStore(project).save(state)
    bootstrap_gate = evaluate_phase_gate(project, "bootstrap")
    if not bootstrap_gate["passed"]:
        raise RuntimeError(f"bootstrap gate failed: {bootstrap_gate['missing_artifacts']}")
    append_jsonl(
        project / ".ai" / "decisions.jsonl",
        {
            "at": utc_now(),
            "decision": "workflow_initialized",
            "mode": mode,
            "frameworks": frameworks,
            "design_mode": design_inputs["mode"],
            "ingested_design_inputs": ingested_design,
        },
    )
    if mode == "brownfield":
        save_inventory(project, inventory(project))
    print_json(state)
    return 0


def command_init(args: argparse.Namespace) -> int:
    return initialize(args, "new")


def command_adopt(args: argparse.Namespace) -> int:
    return initialize(args, "brownfield")


def command_inspect(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    StateStore(project).load()
    report = inventory(project)
    save_inventory(project, report)
    print_json(report if args.deep else report["framework_detection"])
    return 0


def command_reconcile(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state = StateStore(project).load()
    prd_assumption = next(
        (item for item in state.get("assumptions", []) if item.startswith("PRD source: ")), None
    )
    if not prd_assumption:
        raise RuntimeError("state does not record a PRD")
    prd = require_prd(project, prd_assumption.removeprefix("PRD source: "))
    report = inventory(project)
    source_files = (
        [
            path
            for path in report["repository_map"]["files"]
            if not path.startswith((".ai/", "docs/", "HTML/", "artifacts/"))
        ]
        if state["mode"] == "brownfield"
        else []
    )
    requirements = reconcile_requirements(parse_prd(prd), source_files)
    save_requirement_outputs(project, requirements)
    write_json(
        project / "docs" / "generated" / "requirement-reconciliation.json",
        {"version": 1, "requirements": requirements},
    )
    print_json({"requirements": requirements})
    return 0


def command_plan(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state_store = StateStore(project)
    state = state_store.load()
    source = read_json(project / "docs" / "generated" / "requirements.json")
    if not source:
        raise RuntimeError("requirements not found; run ai reconcile first")
    tasks = []
    for priority, requirement in enumerate(source["requirements"], start=1):
        if args.remaining and requirement["status"] == "IMPLEMENTED_VERIFIED":
            continue
        requirement_id = requirement["requirement_id"]
        tasks.append(
            {
                "task_id": f"TASK-{requirement_id}-SLICE",
                "feature_id": requirement_id.lower(),
                "agent": "workflow-orchestrator",
                "priority": priority,
                "requirement_ids": [requirement_id],
                "description": f"Deliver and independently verify {requirement['title']}.",
                "inputs": ["docs/generated/requirements.json", "docs/api/contract-plan.json"],
                "expected_outputs": [
                    "requirement-complete vertical slice",
                    "independent verification evidence",
                ],
                "allowed_paths": [
                    "apps/**",
                    "packages/**",
                    "tests/**",
                    "docs/api/**",
                    ".ai/evidence/**",
                ],
                "forbidden_paths": ["infra/production/**"],
                "dependencies": [],
                "acceptance_criteria": [
                    f"{requirement_id} is implemented and independently verified."
                ],
                "required_tests": ["fast", "affected-full"],
                "security_review_required": False,
                "performance_review_required": False,
                "retry_policy": {"maximum_attempts": 2},
                "context_budget": {"maximum_files": 12, "maximum_characters": 60000},
                "completion_evidence": [
                    "scoped implementation diff",
                    "fast and affected-full check results",
                    "independent final verification",
                ],
                "status": "PLANNED",
            }
        )
    write_json(project / ".ai" / "task-queue.json", {"version": 1, "tasks": tasks})
    state["current_phase"] = "requirements"
    state["status"] = "running"
    state_store.save(state)
    print_json({"planned": len(tasks), "remaining_only": args.remaining})
    return 0


def command_build(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state_store = StateStore(project)
    state = state_store.load()
    queue = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
    selected = [
        task
        for task in queue["tasks"]
        if (not args.feature or task["feature_id"] == args.feature)
        and (not args.remaining or task["status"] not in {"VERIFIED", "COMMITTED"})
    ]
    if args.phase:
        if args.phase not in PHASES:
            raise RuntimeError(f"unknown phase: {args.phase}")
        state["current_phase"] = args.phase
    state["status"] = "running"
    state_store.save(state)
    if args.execute:
        completed = set(state.get("completed_phases", []))
        ready = ready_phases(completed, set())
        phase = args.phase or (ready[0] if ready else None)
        if phase is None:
            raise RuntimeError("no phase is ready for execution")
        if phase not in ready:
            raise RuntimeError(f"phase is not dependency-ready: {phase}; ready={ready}")
        result = execute_phase(
            project,
            phase,
            args.adapter,
            selected,
            commit_verified=args.commit_verified,
            push=args.push,
        )
        print_json(result)
        return 0
    print_json(
        {
            "selected_tasks": [task["task_id"] for task in selected],
            "status": "READY",
            "note": (
                "Dry run only. Repeat with --execute and an installed agent adapter "
                "to execute the next dependency-ready phase."
            ),
        }
    )
    return 0


def command_one_shot(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state_exists = (project / ".ai" / "state.json").is_file()
    if not state_exists:
        prd = require_prd(project, args.prd)
        resolved = resolve_frameworks(
            prd, args.frontend, args.mobile, args.backend, args.deployment
        )
        _require_frameworks("delivery", resolved)
        args.frontend = resolved["frontend"]
        args.mobile = resolved["mobile"]
        args.backend = resolved["backend"]
        args.deployment = resolved["deployment"]
        initialize(args, "new")
    elif args.html or args.screenshot:
        ingest_design_inputs(project, args.html, args.screenshot)
        classify_design_inputs(project)
    if not (project / "docs" / "generated" / "requirements.json").is_file():
        command_reconcile(args)
    if not read_json(project / ".ai" / "task-queue.json", {"tasks": []})["tasks"]:
        command_plan(args)
    queue = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
    selected = [task for task in queue["tasks"] if task["status"] not in {"VERIFIED", "COMMITTED"}]
    if not args.execute:
        print_json(
            {
                "status": "READY",
                "phases": list(PHASES[1:]),
                "tasks": [task["task_id"] for task in selected],
                "note": "Dry run only; repeat with --execute to invoke the selected adapter.",
            }
        )
        return 0
    results = []
    completed = set(StateStore(project).load().get("completed_phases", []))
    for phase in PHASES[1:]:
        if phase in completed:
            continue
        if _skip_disabled_client_phase(project, phase):
            completed.add(phase)
            continue
        results.append(
            execute_phase(
                project,
                phase,
                args.adapter,
                selected,
                commit_verified=args.commit_verified or args.push,
                push=args.push,
            )
        )
        if phase == "requirements":
            refreshed = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
            selected = [
                task
                for task in refreshed["tasks"]
                if task["status"] not in {"VERIFIED", "COMMITTED"}
            ]
    print_json({"status": "complete", "phases": results})
    return 0


def _apply_framework_selections(project: Path, args: argparse.Namespace) -> None:
    store = StateStore(project)
    state = store.load()
    for side in ("frontend", "mobile", "backend", "deployment"):
        selected = getattr(args, side, "unknown")
        current = state["frameworks"][side]
        if selected == "unknown":
            continue
        if current != "unknown" and current != selected:
            raise RuntimeError(f"cannot change {side} framework from {current} to {selected}")
        state["frameworks"][side] = selected
        completed = state.get("completed_phases", [])
        if current == "unknown" and side in completed:
            phase_index = PHASES.index(side)
            state["completed_phases"] = [
                phase for phase in completed if PHASES.index(phase) < phase_index
            ]
            state["status"] = "running"
    store.save(state)


def _require_frameworks(target: str, frameworks: dict[str, str]) -> None:
    missing: list[str] = []
    if target == "frontend" and frameworks["frontend"] == "unknown":
        missing.append("frontend: react or nextjs")
    elif target == "mobile" and frameworks["mobile"] == "unknown":
        missing.append("mobile: flutter")
    elif target not in {"design-spec", "html"}:
        if frameworks["frontend"] == "unknown" and frameworks["mobile"] == "unknown":
            missing.append("client: react, nextjs, or flutter")
        if frameworks["backend"] == "unknown":
            missing.append("backend: django-drf or fastapi")
    if target == "deployment" and frameworks["deployment"] == "unknown":
        missing.append("deployment provider: aws")
    if missing:
        raise RuntimeError(f"framework selection required ({'; '.join(missing)})")


def _skip_disabled_client_phase(project: Path, phase: str) -> bool:
    side = phase if phase in {"frontend", "mobile", "deployment"} else None
    if side is None:
        return False
    store = StateStore(project)
    state = store.load()
    if state["frameworks"][side] != "unknown":
        return False
    completed = state.setdefault("completed_phases", [])
    if phase not in completed:
        completed.append(phase)
    state["current_phase"] = phase
    store.save(state)
    append_jsonl(
        project / ".ai" / "decisions.jsonl",
        {"at": utc_now(), "decision": "optional_phase_skipped", "phase": phase},
    )
    return True


def _verify_resume_boundary(project: Path) -> None:
    state = StateStore(project).load()
    current = baseline(project)
    if not current["is_repository"]:
        raise RuntimeError("cannot resume because the target is no longer a Git repository")
    branch = current["branch"] if isinstance(current["branch"], str) else None
    recorded = state.get("git", {}).get("branch")
    assert_safe_branch(branch)
    if not isinstance(recorded, str) or branch != recorded:
        raise RuntimeError(f"resume branch mismatch: recorded={recorded}, current={branch}")


def command_start(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    validate_control_plane()
    target = args.until
    if not (project / ".ai" / "state.json").is_file():
        prd = discover_prd(project, args.prd)
        args.prd = prd.relative_to(project).as_posix()
        resolved = resolve_frameworks(
            prd, args.frontend, args.mobile, args.backend, args.deployment
        )
        args.frontend = resolved["frontend"]
        args.mobile = resolved["mobile"]
        args.backend = resolved["backend"]
        args.deployment = resolved["deployment"]
        _require_frameworks(target, resolved)
        if not baseline(project)["is_repository"] and not args.github_user:
            raise RuntimeError("--github-user is required to create a safe feature branch")
        initialize(args, "new")
    else:
        _verify_resume_boundary(project)
        if args.html or args.screenshot:
            ingest_design_inputs(project, args.html, args.screenshot)
            classify_design_inputs(project)
        _apply_framework_selections(project, args)
        _require_frameworks(target, StateStore(project).load()["frameworks"])

    if not (project / "docs" / "generated" / "requirements.json").is_file():
        command_reconcile(args)
    if not read_json(project / ".ai" / "task-queue.json", {"tasks": []})["tasks"]:
        command_plan(args)
    queue = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
    selected = [task for task in queue["tasks"] if task["status"] not in {"VERIFIED", "COMMITTED"}]
    completed = set(StateStore(project).load().get("completed_phases", []))
    results = []
    terminal_phase = "design" if target in {"design-spec", "html"} else target
    for phase in PHASES[1:]:
        if target == "mobile" and phase == "frontend" and phase not in completed:
            continue
        if phase in completed:
            if phase == terminal_phase:
                break
            continue
        if _skip_disabled_client_phase(project, phase):
            completed.add(phase)
            if phase == terminal_phase:
                break
            continue
        if phase in {"frontend", "mobile", "backend", "deployment"}:
            state = StateStore(project).load()
            if state["frameworks"][phase] == "unknown":
                raise RuntimeError(f"--{phase} is required before starting the {phase} phase")
        stop_after = (
            "create-design-specification" if target == "design-spec" and phase == "design" else None
        )
        results.append(
            execute_phase(
                project,
                phase,
                args.adapter,
                selected,
                commit_verified=args.commit_verified or args.push,
                push=args.push,
                stop_after_node=stop_after,
            )
        )
        if phase == "requirements":
            refreshed = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
            selected = [
                task
                for task in refreshed["tasks"]
                if task["status"] not in {"VERIFIED", "COMMITTED"}
            ]
        if phase == terminal_phase:
            break
    status = "complete" if target == "delivery" else "stopped-at-requested-stage"
    print_json({"status": status, "requested_stage": target, "results": results})
    return 0


def command_verify(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state = StateStore(project).load()
    evidence_root = project / ".ai" / "evidence" / "features"
    feature_paths = (
        [evidence_root / args.feature] if args.feature else list(evidence_root.glob("*"))
    )
    findings = []
    for feature in feature_paths:
        verification = feature / "final-verification.json"
        payload = read_json(verification)
        findings.append(
            {
                "feature": feature.name,
                "verified": bool(payload and payload.get("verified") is True),
                "evidence": str(verification.relative_to(project))
                if verification.exists()
                else None,
            }
        )
    passed = bool(findings) and all(item["verified"] for item in findings)
    print_json({"project": state["project_id"], "passed": passed, "features": findings})
    return 0 if passed else 2


def command_test(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    manifest = read_json(project / ".ai" / "test-commands.json", {"commands": {}})
    scope = "all" if args.all else args.scope
    commands = manifest.get("commands", {}).get(scope, [])
    if not commands:
        print_json(
            {
                "scope": scope,
                "status": "not-run",
                "reason": "No approved deterministic test commands are configured.",
            }
        )
        return 2
    if args.execute:
        if scope == "all":
            configured = manifest.get("commands", {})
            groups = [
                group
                for group in ("backend", "frontend", "mobile", "contract", "integration", "e2e")
                if isinstance(configured, dict) and configured.get(group)
            ]
        else:
            groups = [scope]
        print_json(run_command_groups(project, groups))
        return 0
    print_json({"scope": scope, "status": "dry-run", "commands": commands})
    return 0


def command_review(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    report = inventory(project)
    findings = report["risks"]
    write_json(
        project / "artifacts" / "final" / "review-findings.json",
        {"generated_at": utc_now(), "findings": findings},
    )
    print_json(
        {"passed": not any(item["severity"] == "high" for item in findings), "findings": findings}
    )
    return 0 if not any(item["severity"] == "high" for item in findings) else 2


def command_status(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    state = StateStore(project).load()
    queue = read_json(project / ".ai" / "task-queue.json", {"tasks": []})
    payload = {"state": state, "task_count": len(queue["tasks"]), "tasks": queue["tasks"]}
    if args.json:
        print_json(payload)
    else:
        print(f"{state['project_id']}: {state['status']} / {state['current_phase']}")
        print(f"tasks: {len(queue['tasks'])}")
    return 0


def command_resume(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    store = StateStore(project)
    state = store.load()
    if state["status"] == "complete":
        print_json({"status": "complete", "message": "Nothing to resume."})
        return 0
    state["status"] = "running"
    store.save(state)
    append_jsonl(project / ".ai" / "decisions.jsonl", {"at": utc_now(), "decision": "resumed"})
    print_json({"status": "running", "phase": state["current_phase"]})
    return 0


def command_push(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    git = baseline(project)
    branch = git["branch"] if isinstance(git["branch"], str) else None
    if branch is None:
        raise RuntimeError("a named Git branch is required")
    assert_safe_branch(branch)
    if git["dirty"]:
        raise RuntimeError("working tree must be clean before push")
    remote_code, remote = run_git(project, "remote", "get-url", args.remote)
    if remote_code != 0 or not remote:
        raise RuntimeError(f"Git remote is not configured: {args.remote}")
    payload = {"remote": args.remote, "branch": branch, "url": remote, "execute": args.execute}
    if not args.execute:
        payload["status"] = "dry-run"
        print_json(payload)
        return 0
    code, output = run_git(project, "push", "--set-upstream", args.remote, branch)
    payload.update({"status": "pushed" if code == 0 else "failed", "output": output})
    print_json(payload)
    return code


def command_doctor(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    git_path = shutil.which("git")
    checks = {
        "python": python_version,
        "git": git_path,
        "docker": shutil.which("docker"),
        "node": shutil.which("node"),
        "npm": shutil.which("npm"),
        "workflow_initialized": (project / ".ai" / "state.json").is_file(),
    }
    print_json(checks)
    return 0 if sys.version_info >= (3, 12) and git_path else 2


def command_pipeline(args: argparse.Namespace) -> int:
    print_json(validate_control_plane())
    return 0


def command_clean_state(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    target = project / ".ai"
    if not args.yes:
        raise RuntimeError("clean-state is destructive; repeat with --yes")
    if target.resolve().parent != project:
        raise RuntimeError("refusing unsafe state target")
    if target.exists():
        shutil.rmtree(target)
    print_json({"removed": str(target), "recoverable": False})
    return 0


def command_generate_prd(args: argparse.Namespace) -> int:
    code, payload = generate_prd(
        resolved_project(args.project),
        args.requirements,
        args.output,
        args.answer,
        args.adapter,
    )
    print_json(payload)
    return code


def command_resolve_token(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)
    print_json(
        resolve_token(
            project,
            args.token,
            args.adapter,
            approve=args.approve,
            github_user=args.github_user,
            remote=args.remote,
        )
    )
    return 0


def command_sync_design(args: argparse.Namespace) -> int:
    code, payload = sync_design(
        resolved_project(args.project),
        args.adapter,
        args.target,
        check_only=args.check_only,
        allow_baseline_update=args.allow_baseline_update,
    )
    print_json(payload)
    return code


def command_compare_images(args: argparse.Namespace) -> int:
    project = resolved_project(args.project)

    def project_path(value: str) -> Path:
        path = (project / value).resolve()
        if path != project and project not in path.parents:
            raise RuntimeError(f"image comparison path escapes project: {value}")
        return path

    reference = project_path(args.reference)
    actual = project_path(args.actual)
    difference = project_path(args.diff)
    metrics_path = project_path(args.metrics)
    paths = [reference, actual, difference, metrics_path]
    if len(set(paths)) != len(paths):
        raise RuntimeError("reference, actual, diff, and metrics paths must be distinct")
    metrics = compare_pixels(
        reference,
        actual,
        diff_path=difference,
        channel_tolerance=args.channel_tolerance,
        max_changed_ratio=args.max_changed_ratio,
        masks=[parse_mask(value) for value in args.mask],
    )
    write_json(metrics_path, metrics)
    print_json(metrics)
    return 0 if metrics["passed"] else 2


def command_deployment_status(args: argparse.Namespace) -> int:
    print_json(deployment_status(resolved_project(args.project)))
    return 0


def command_deployment_operation(args: argparse.Namespace) -> int:
    operation = "rollback" if args.command == "rollback-deployment" else "deploy"
    environment = (
        args.environment if operation == "rollback" else args.command.removeprefix("deploy-")
    )
    approved = bool(
        getattr(args, "approve_production", False) or getattr(args, "approve_rollback", False)
    )
    print_json(
        execute_operation(
            resolved_project(args.project), environment, operation, args.execute, approved
        )
    )
    return 0


def add_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")


def add_start_arguments(command: argparse.ArgumentParser, until: str) -> None:
    add_project(command)
    command.add_argument("--prd")
    command.add_argument("--project-id")
    command.add_argument("--github-user")
    command.add_argument("--branch-feature")
    command.add_argument("--html", action="append", default=[])
    command.add_argument("--screenshot", action="append", default=[])
    command.add_argument("--frontend", choices=["react", "nextjs", "unknown"], default="unknown")
    command.add_argument("--mobile", choices=["flutter", "unknown"], default="unknown")
    command.add_argument(
        "--backend", choices=["django-drf", "fastapi", "unknown"], default="unknown"
    )
    command.add_argument("--deployment", choices=["aws", "unknown"], default="unknown")
    command.add_argument("--adapter", choices=["codex"], default="codex")
    command.add_argument("--commit-verified", action="store_true")
    command.add_argument("--push", action="store_true")
    command.add_argument("--remaining", action="store_true", default=True)
    command.set_defaults(handler=command_start, until=until)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ai", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name, handler in (("init", command_init), ("adopt", command_adopt)):
        command = commands.add_parser(name)
        add_project(command)
        command.add_argument("--prd", required=True)
        command.add_argument("--project-id")
        command.add_argument("--github-user")
        command.add_argument("--branch-feature")
        command.add_argument("--html", action="append", default=[])
        command.add_argument("--screenshot", action="append", default=[])
        command.add_argument(
            "--frontend", choices=["react", "nextjs", "unknown"], default="unknown"
        )
        command.add_argument("--mobile", choices=["flutter", "unknown"], default="unknown")
        command.add_argument(
            "--backend", choices=["django-drf", "fastapi", "unknown"], default="unknown"
        )
        command.add_argument("--deployment", choices=["aws", "unknown"], default="unknown")
        command.set_defaults(handler=handler)
    one_shot = commands.add_parser("one-shot")
    add_project(one_shot)
    one_shot.add_argument("--prd", required=True)
    one_shot.add_argument("--project-id")
    one_shot.add_argument("--github-user")
    one_shot.add_argument("--branch-feature")
    one_shot.add_argument("--html", action="append", default=[])
    one_shot.add_argument("--screenshot", action="append", default=[])
    one_shot.add_argument("--frontend", choices=["react", "nextjs", "unknown"], default="unknown")
    one_shot.add_argument("--mobile", choices=["flutter", "unknown"], default="unknown")
    one_shot.add_argument("--backend", choices=["django-drf", "fastapi"], required=True)
    one_shot.add_argument("--deployment", choices=["aws", "unknown"], default="unknown")
    one_shot.add_argument("--adapter", choices=["codex"], default="codex")
    one_shot.add_argument("--execute", action="store_true")
    one_shot.add_argument("--commit-verified", action="store_true")
    one_shot.add_argument("--push", action="store_true")
    one_shot.add_argument("--remaining", action="store_true", default=True)
    one_shot.set_defaults(handler=command_one_shot)
    start_commands = {
        "start-design": "design-spec",
        "start-generatehtml": "html",
        "start-frontend": "frontend",
        "start-mobile": "mobile",
        "start-backend": "backend",
        "start-integration": "integration",
        "start-testing": "testing",
        "start-deployment": "deployment",
        "start-delivery": "delivery",
        "start-build": "delivery",
        "resume-build": "delivery",
    }
    for name, until in start_commands.items():
        add_start_arguments(commands.add_parser(name), until)
    inspect = commands.add_parser("inspect")
    add_project(inspect)
    inspect.add_argument("--deep", action="store_true")
    inspect.set_defaults(handler=command_inspect)
    reconcile = commands.add_parser("reconcile")
    add_project(reconcile)
    reconcile.set_defaults(handler=command_reconcile)
    plan = commands.add_parser("plan")
    add_project(plan)
    plan.add_argument("--remaining", action="store_true")
    plan.set_defaults(handler=command_plan)
    build = commands.add_parser("build")
    add_project(build)
    build.add_argument("--phase")
    build.add_argument("--feature")
    build.add_argument("--remaining", action="store_true")
    build.add_argument("--execute", action="store_true")
    build.add_argument("--adapter", choices=["codex"], default="codex")
    build.add_argument("--commit-verified", action="store_true")
    build.add_argument("--push", action="store_true")
    build.set_defaults(handler=command_build)
    verify = commands.add_parser("verify")
    add_project(verify)
    verify.add_argument("--feature")
    verify.add_argument("--remaining", action="store_true")
    verify.set_defaults(handler=command_verify)
    test = commands.add_parser("test")
    add_project(test)
    selection = test.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument(
        "--scope", choices=["backend", "frontend", "mobile", "contract", "integration", "e2e"]
    )
    test.set_defaults(handler=command_test)
    test.add_argument("--execute", action="store_true")
    review = commands.add_parser("review")
    add_project(review)
    review.set_defaults(handler=command_review)
    status = commands.add_parser("status")
    add_project(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)
    resume = commands.add_parser("resume")
    add_project(resume)
    resume.set_defaults(handler=command_resume)
    push = commands.add_parser("push")
    add_project(push)
    push.add_argument("--remote", default="origin")
    push.add_argument("--execute", action="store_true")
    push.set_defaults(handler=command_push)
    doctor = commands.add_parser("doctor")
    add_project(doctor)
    doctor.set_defaults(handler=command_doctor)
    pipeline = commands.add_parser("pipeline")
    pipeline.set_defaults(handler=command_pipeline)
    clean = commands.add_parser("clean-state")
    add_project(clean)
    clean.add_argument("--yes", action="store_true")
    clean.set_defaults(handler=command_clean_state)
    prd = commands.add_parser("generate-prd")
    add_project(prd)
    prd.add_argument("--requirements", required=True)
    prd.add_argument("--output", default="PRD.md")
    prd.add_argument("--answer", action="append", default=[])
    prd.add_argument("--adapter", choices=["codex"], default="codex")
    prd.set_defaults(handler=command_generate_prd)
    token = commands.add_parser("resolve-token")
    add_project(token)
    token.add_argument("--token", required=True)
    token.add_argument("--adapter", choices=["codex"], default="codex")
    token.add_argument("--approve", action="store_true")
    token.add_argument("--github-user")
    token.add_argument("--remote", default="origin")
    token.set_defaults(handler=command_resolve_token)
    design_sync = commands.add_parser("sync-design")
    add_project(design_sync)
    design_sync.add_argument("--target", choices=["all", "frontend", "mobile"], default="all")
    design_sync.add_argument("--adapter", choices=["codex"], default="codex")
    design_sync.add_argument("--check-only", action="store_true")
    design_sync.add_argument("--allow-baseline-update", action="store_true")
    design_sync.set_defaults(handler=command_sync_design)
    compare = commands.add_parser("compare-images")
    add_project(compare)
    compare.add_argument("--reference", required=True)
    compare.add_argument("--actual", required=True)
    compare.add_argument("--diff", required=True)
    compare.add_argument("--metrics", required=True)
    compare.add_argument("--channel-tolerance", type=int, default=0)
    compare.add_argument("--max-changed-ratio", type=float, default=0.0)
    compare.add_argument("--mask", action="append", default=[])
    compare.set_defaults(handler=command_compare_images)
    deployment_status_command = commands.add_parser("deployment-status")
    add_project(deployment_status_command)
    deployment_status_command.set_defaults(handler=command_deployment_status)
    for name in ("deploy-staging", "deploy-production"):
        deployment = commands.add_parser(name)
        add_project(deployment)
        deployment.add_argument("--execute", action="store_true")
        deployment.add_argument("--approve-production", action="store_true")
        deployment.set_defaults(handler=command_deployment_operation)
    rollback = commands.add_parser("rollback-deployment")
    add_project(rollback)
    rollback.add_argument("--environment", choices=["staging", "production"], required=True)
    rollback.add_argument("--execute", action="store_true")
    rollback.add_argument("--approve-rollback", action="store_true")
    rollback.set_defaults(handler=command_deployment_operation)
    return root


def main(arguments: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(arguments)
        handler: Command = args.handler
        return handler(args)
    except (RuntimeError, ValueError, OSError) as error:
        print(
            json.dumps({"error": {"code": "WORKFLOW_ERROR", "message": str(error)}}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
