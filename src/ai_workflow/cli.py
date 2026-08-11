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
from .discovery import inventory, print_json, save_inventory
from .execution import evaluate_phase_gate, execute_phase
from .git import assert_safe_branch, baseline, prepare_feature_branch, run_git
from .io import append_jsonl, read_json, write_json
from .model import PHASES, StateStore, utc_now
from .pipeline import ready_phases, validate_control_plane
from .requirements import parse_prd, save_requirement_outputs
from .requirements import reconcile as reconcile_requirements

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


def initialize(args: argparse.Namespace, mode: str) -> int:
    project = resolved_project(args.project)
    prd = require_prd(project, args.prd)
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
    frameworks = {"frontend": args.frontend, "backend": args.backend}
    if mode == "brownfield":
        report = inventory(project)
        detected = report["framework_detection"]
        for side in ("frontend", "backend"):
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
    )
    save_inventory(project, inventory(project))
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
        initialize(args, "new")
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
        groups = (
            ["backend", "frontend", "contract", "integration", "e2e"] if scope == "all" else [scope]
        )
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


def add_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")


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
        command.add_argument(
            "--frontend", choices=["react", "nextjs", "unknown"], default="unknown"
        )
        command.add_argument(
            "--backend", choices=["django-drf", "fastapi", "unknown"], default="unknown"
        )
        command.set_defaults(handler=handler)
    one_shot = commands.add_parser("one-shot")
    add_project(one_shot)
    one_shot.add_argument("--prd", required=True)
    one_shot.add_argument("--project-id")
    one_shot.add_argument("--github-user")
    one_shot.add_argument("--branch-feature")
    one_shot.add_argument("--frontend", choices=["react", "nextjs"], required=True)
    one_shot.add_argument("--backend", choices=["django-drf", "fastapi"], required=True)
    one_shot.add_argument("--adapter", choices=["claude", "opencode", "codex"], default="claude")
    one_shot.add_argument("--execute", action="store_true")
    one_shot.add_argument("--commit-verified", action="store_true")
    one_shot.add_argument("--push", action="store_true")
    one_shot.add_argument("--remaining", action="store_true", default=True)
    one_shot.set_defaults(handler=command_one_shot)
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
    build.add_argument("--adapter", choices=["claude", "opencode", "codex"], default="claude")
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
        "--scope", choices=["backend", "frontend", "contract", "integration", "e2e"]
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
