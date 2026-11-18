"""Explicit review-PR merges and safe workflow-repository synchronization."""

from __future__ import annotations

import configparser
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .io import read_json, write_json

_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_PR = re.compile(r"^pr-([1-9][0-9]*)$", re.I)
_GITHUB = re.compile(r"^(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_PASSING = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_ALIASES = {"react": "reactjs", "django": "drf"}


def _run(cwd: Path, *argv: str, allow_failure: bool = False) -> tuple[int, str]:
    executable = shutil.which(argv[0])
    if executable is None:
        raise RuntimeError(f"required executable is unavailable: {argv[0]}")
    result = subprocess.run(  # noqa: S603 - fixed executable and argument vectors
        [executable, *argv[1:]], cwd=cwd, capture_output=True, text=True,
        check=False, timeout=120,
    )
    output = (result.stdout if result.returncode == 0 else result.stderr or result.stdout).strip()
    if result.returncode and not allow_failure:
        raise RuntimeError(f"{argv[0]} {' '.join(argv[1:3])} failed in {cwd}: {output[-800:]}")
    return result.returncode, output


def _git(repo: Path, *args: str) -> str:
    return _run(repo, "git", *args)[1]


def _repo_root(project: Path) -> tuple[Path, bool]:
    """Return agents checkout and whether it is embedded in a project."""
    project = project.resolve()
    if (project / ".agents" / ".gitmodules").is_file():
        return project / ".agents", True
    if (project / "agents" / ".gitmodules").is_file():
        return project / "agents", False
    if (project / ".gitmodules").is_file() and (project / "src/ai_workflow").is_dir():
        return project, False
    raise RuntimeError("git maintenance requires a project with .agents or the workflow workspace")


def _catalog(root: Path) -> dict[str, dict[str, str]]:
    config = configparser.ConfigParser()
    config.read(root / ".gitmodules")
    result: dict[str, dict[str, str]] = {}
    for section in config.sections():
        if not section.startswith('submodule "') or not section.endswith('"'):
            continue
        name = section.removeprefix('submodule "').removesuffix('"')
        path = config.get(section, "path", fallback="")
        url = config.get(section, "url", fallback="")
        branch = config.get(section, "branch", fallback="")
        if not _NAME.fullmatch(name) or path != name or not _GITHUB.fullmatch(url):
            raise RuntimeError(f"unsafe workflow submodule declaration: {section}")
        if branch != "dev":
            raise RuntimeError(f"workflow repository must use the dev branch: {section}")
        result[name] = {"url": url, "branch": branch}
    root_url = _git(root, "remote", "get-url", "origin")
    if not _GITHUB.fullmatch(root_url):
        raise RuntimeError("agents origin must be a GitHub repository")
    result["agents"] = {"url": root_url, "branch": "dev"}
    return result


def _name(value: str, catalog: dict[str, dict[str, str]]) -> str:
    name = _ALIASES.get(value.lower(), value.lower())
    if name not in catalog:
        raise RuntimeError(f"unknown workflow repository: {value}")
    return name


def _github_repository(url: str) -> str:
    match = _GITHUB.fullmatch(url)
    if match is None:
        raise RuntimeError(f"unsupported workflow remote: {url}")
    return f"{match.group(1)}/{match.group(2)}"


def _proposal_for(project: Path, url: str) -> tuple[Path, dict[str, Any]] | None:
    directory = project / ".ai/workflow-pr-proposals"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        payload = read_json(path, {})
        if isinstance(payload, dict) and payload.get("pr_url") == url:
            return path, payload
    return None


def _pending_targets(project: Path, catalog: dict[str, dict[str, str]]) -> list[tuple[str, int]]:
    directory = project / ".ai/workflow-pr-proposals"
    targets: list[tuple[str, int]] = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        payload = read_json(path, {})
        if not isinstance(payload, dict) or payload.get("status") not in {
            "PR_OPEN", "AWAITING_MERGE_APPROVAL",
        }:
            continue
        approval = payload.get("merge_approval")
        if not isinstance(approval, dict) or approval.get("status") != "required":
            continue
        url = payload.get("pr_url", "")
        match = re.fullmatch(
            r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)",
            str(url),
        )
        if match is None:
            raise RuntimeError(f"invalid pending workflow PR URL: {path}")
        name = _name(match.group(2), catalog)
        expected = f"{match.group(1)}/{match.group(2)}"
        if _github_repository(catalog[name]["url"]).lower() != expected.lower():
            raise RuntimeError(f"pending workflow PR does not match the catalog: {path}")
        targets.append((name, int(match.group(3))))
    return targets


def _checks_passed(rollup: Any) -> bool:
    if not isinstance(rollup, list):
        return False
    return all(
        isinstance(check, dict)
        and (check.get("conclusion") or check.get("state")) in _PASSING
        for check in rollup
    )


def _pr_view(cwd: Path, repository: str, number: int) -> dict[str, Any]:
    raw = _run(
        cwd, "gh", "pr", "view", str(number), "--repo", repository,
        "--json", (
            "state,baseRefName,headRefOid,mergeable,mergeCommit,"
            "statusCheckRollup,reviewDecision,url"
        ),
    )[1]
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned an invalid PR response")
    return payload


def merge_workflow_prs(project: Path, arguments: list[str]) -> dict[str, Any]:
    """Merge explicitly named PRs, or every recorded pending workflow-repair PR."""
    root, _ = _repo_root(project)
    catalog = _catalog(root)
    if arguments:
        if len(arguments) % 2:
            raise RuntimeError("use repository/PR pairs, for example: base pr-2 agents pr-6")
        targets: list[tuple[str, int]] = []
        for index in range(0, len(arguments), 2):
            name = _name(arguments[index], catalog)
            match = _PR.fullmatch(arguments[index + 1])
            if match is None:
                raise RuntimeError(f"invalid PR number: {arguments[index + 1]}")
            targets.append((name, int(match.group(1))))
    else:
        targets = _pending_targets(project, catalog)
    if not targets:
        return {"status": "nothing-to-merge", "merged": []}
    if len(set(targets)) != len(targets):
        raise RuntimeError("duplicate PR target")
    # Framework/base changes must land before agents PRs that pin them.
    targets.sort(key=lambda item: (item[0] == "agents", item[0], item[1]))
    prepared: list[tuple[str, int, str, str, str]] = []
    for name, number in targets:
        repository = _github_repository(catalog[name]["url"])
        current = _pr_view(root, repository, number)
        url = f"https://github.com/{repository}/pull/{number}"
        proposal = _proposal_for(project, url)
        if current.get("state") != "OPEN":
            raise RuntimeError(f"PR is not open: {url}")
        if current.get("baseRefName") != catalog[name]["branch"]:
            raise RuntimeError(f"PR targets an unexpected base branch: {url}")
        if current.get("mergeable") != "MERGEABLE":
            raise RuntimeError(f"PR is not currently mergeable: {url}")
        if current.get("reviewDecision") in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
            raise RuntimeError(f"PR review has not passed: {url}")
        if not _checks_passed(current.get("statusCheckRollup")):
            raise RuntimeError(f"PR checks are pending or failing: {url}")
        head = current.get("headRefOid")
        if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
            raise RuntimeError(f"PR has no stable head commit: {url}")
        if proposal is not None and proposal[1].get("commit") not in {None, head}:
            raise RuntimeError(f"PR head changed since project approval: {url}")
        prepared.append((name, number, repository, url, head))
    merged: list[dict[str, str]] = []
    for name, number, repository, url, head in prepared:
        try:
            current = _pr_view(root, repository, number)
            if current.get("state") != "OPEN" or current.get("headRefOid") != head:
                raise RuntimeError(f"PR changed after preflight: {url}")
            if (
                current.get("mergeable") != "MERGEABLE"
                or not _checks_passed(current.get("statusCheckRollup"))
            ):
                raise RuntimeError(f"PR checks or mergeability changed: {url}")
            _run(root, "gh", "pr", "merge", str(number), "--repo", repository,
                 "--merge", "--match-head-commit", head)
            confirmed = _pr_view(root, repository, number)
            commit = confirmed.get("mergeCommit")
            if (
                confirmed.get("state") != "MERGED"
                or not isinstance(commit, dict)
                or not commit.get("oid")
            ):
                raise RuntimeError(f"GitHub did not confirm a merge commit: {url}")
            proposal = _proposal_for(project, url)
            if proposal is not None:
                path, payload = proposal
                payload.update(status="MERGED", merge_commit=commit["oid"])
                payload["merge_approval"] = {"status": "approved"}
                write_json(path, payload)
            merged.append({"repository": name, "pr_url": url, "merge_commit": commit["oid"]})
        except RuntimeError as error:
            completed = ", ".join(item["pr_url"] for item in merged) or "none"
            raise RuntimeError(
                f"{error}; PRs already merged in this invocation: {completed}"
            ) from error
    return {"status": "merged", "merged": merged}


def _clean(repo: Path) -> None:
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError(f"repository has local changes; commit or stash first: {repo}")
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        path = Path(_git(repo, "rev-parse", "--git-path", marker))
        if (path if path.is_absolute() else repo / path).exists():
            raise RuntimeError(f"repository has an unfinished Git operation: {repo}")


def _assert_origin(repo: Path, expected: str) -> None:
    actual = _git(repo, "remote", "get-url", "origin")
    if _github_repository(actual).lower() != _github_repository(expected).lower():
        raise RuntimeError(f"origin remote does not match the workflow catalog: {repo}")


def _prepare_branch(repo: Path, branch: str) -> str:
    _run(
        repo, "git", "-c", "fetch.recurseSubmodules=false",
        "fetch", "--no-tags", "origin", branch,
    )
    target = _git(repo, "rev-parse", "FETCH_HEAD")
    current = _git(repo, "rev-parse", "HEAD")
    if _run(repo, "git", "merge-base", "--is-ancestor", current, target, allow_failure=True)[0]:
        raise RuntimeError(
            f"repository has commits that do not fast-forward to origin/{branch}: {repo}"
        )
    active = _git(repo, "branch", "--show-current")
    if active and active != branch:
        raise RuntimeError(f"repository is on {active}; switch to {branch} explicitly: {repo}")
    return target


def _sync_branch(repo: Path, branch: str, target: str | None = None) -> str:
    target = target or _prepare_branch(repo, branch)
    _clean(repo)
    current = _git(repo, "rev-parse", "HEAD")
    if _run(repo, "git", "merge-base", "--is-ancestor", current, target, allow_failure=True)[0]:
        raise RuntimeError(f"repository changed after pull preflight: {repo}")
    active = _git(repo, "branch", "--show-current")
    if active:
        _git(repo, "merge", "--ff-only", target)
    else:
        _git(repo, "checkout", "--detach", target)
    return target


def _pinned(root: Path, name: str, revision: str = "HEAD") -> str:
    raw = _git(root, "ls-tree", revision, "--", name)
    match = re.fullmatch(r"160000 commit ([0-9a-f]{40})\t.+", raw)
    if match is None:
        raise RuntimeError(f"agents does not pin a valid {name} submodule")
    return match.group(1)


def _prepare_pin(root: Path, name: str, entry: dict[str, str], revision: str) -> str:
    target = _pinned(root, name, revision)
    path = root / name
    if not path.is_dir() or not (path / ".git").exists():
        return target  # initialization is handled when applying the reviewed pin
    _clean(path)
    _assert_origin(path, entry["url"])
    _run(
        path, "git", "-c", "fetch.recurseSubmodules=false",
        "fetch", "--no-tags", "origin", "dev",
    )
    if _run(path, "git", "cat-file", "-e", f"{target}^{{commit}}", allow_failure=True)[0]:
        raise RuntimeError(f"pinned commit is not available from {name}/dev")
    dev_head = _git(path, "rev-parse", "FETCH_HEAD")
    if _run(path, "git", "merge-base", "--is-ancestor", target, dev_head,
            allow_failure=True)[0]:
        raise RuntimeError(f"{name} pin is not reachable from its dev branch")
    current = _git(path, "rev-parse", "HEAD")
    if _run(path, "git", "merge-base", "--is-ancestor", current, target, allow_failure=True)[0]:
        raise RuntimeError(f"{name} has commits outside its reviewed agents pin")
    return target


def _sync_pinned(root: Path, name: str, entry: dict[str, str], target: str) -> str:
    path = root / name
    if not path.is_dir() or not (path / ".git").exists():
        _git(root, "submodule", "update", "--init", "--", name)
        _prepare_pin(root, name, entry, "HEAD")
    _clean(path)
    _assert_origin(path, entry["url"])
    current = _git(path, "rev-parse", "HEAD")
    if _run(path, "git", "merge-base", "--is-ancestor", current, target, allow_failure=True)[0]:
        raise RuntimeError(f"{name} changed after pin preflight")
    _git(path, "checkout", "--detach", target)
    return target


def pull_workflow_repos(project: Path, requested: list[str]) -> dict[str, Any]:
    """Fast-forward workflow clones or sync project submodules to reviewed pins."""
    root, embedded = _repo_root(project)
    catalog = _catalog(root)
    names = (
        list(dict.fromkeys(_name(value, catalog) for value in requested))
        if requested else list(catalog)
    )
    if "agents" in names:
        names = list(catalog)  # a new agents pin requires a complete, consistent submodule set
    targets: dict[str, Path] = {"agents": root}
    if embedded or root == project.resolve():
        targets.update({name: root / name for name in catalog if name != "agents"})
    else:
        targets.update({name: root.parent / name for name in catalog if name != "agents"})
    for name in names:
        path = targets[name]
        if not path.is_dir() or not (path / ".git").exists():
            if not embedded or name == "agents":
                raise RuntimeError(f"workflow repository is not initialized: {path}")
            continue  # _sync_pinned initializes an embedded submodule
        _clean(path)
        _assert_origin(path, catalog[name]["url"])
        active = _git(path, "branch", "--show-current")
        if active and active != catalog[name]["branch"]:
            raise RuntimeError(f"repository is on {active}; switch branches explicitly: {path}")
    workspace = not embedded and root != project.resolve()
    branch_targets: dict[str, str] = {}
    if "agents" in names:
        branch_targets["agents"] = _prepare_branch(root, catalog["agents"]["branch"])
    if workspace:
        for name in names:
            if name != "agents":
                branch_targets[name] = _prepare_branch(
                    targets[name], catalog[name]["branch"]
                )
    pinned_targets: dict[str, str] = {}
    if not workspace or "agents" in names:
        revision = branch_targets.get("agents", "HEAD")
        pinned_names = [name for name in names if name != "agents"]
        for name in pinned_names:
            pinned_targets[name] = _prepare_pin(root, name, catalog[name], revision)
    updated: list[dict[str, str]] = []
    if "agents" in names:
        commit = _sync_branch(root, catalog["agents"]["branch"], branch_targets["agents"])
        updated.append({"repository": "agents", "commit": commit})
        if workspace:
            for name, entry in catalog.items():
                if name != "agents":
                    _sync_pinned(root, name, entry, pinned_targets[name])
    for name in names:
        if name == "agents":
            continue
        if embedded or root == project.resolve():
            commit = _sync_pinned(root, name, catalog[name], pinned_targets[name])
        else:
            commit = _sync_branch(
                targets[name], catalog[name]["branch"], branch_targets[name]
            )
        updated.append({"repository": name, "commit": commit})
    return {
        "status": "updated",
        "mode": "project-pins" if embedded or root == project.resolve() else "workflow-workspace",
        "updated": updated,
    }
