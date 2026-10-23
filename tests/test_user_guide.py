import argparse
import json
import re
from pathlib import Path

from ai_workflow.cli import parser


def test_user_guide_covers_catalog_and_cli_flags_in_workflow_order() -> None:
    root = Path(__file__).resolve().parents[1]
    document = (root / "USER_GUIDE.md").read_text()
    catalog = json.loads((root / "skills" / "catalog.json").read_text())
    catalog_names = [item["name"] for item in catalog["skills"]]
    skill_names = set(catalog_names)
    for name in skill_names:
        assert f"### `${name}`" in document

    cli = parser()
    subparsers = next(
        action for action in cli._actions if isinstance(action, argparse._SubParsersAction)
    )
    command_names = {
        "workflow-status": "status",
        **{
            name: name
            for name in skill_names
            if name not in {"workflow-status", "create-requirements"}
        },
    }
    for command in command_names.values():
        command_parser = subparsers.choices[command]
        flags = {
            flag
            for action in command_parser._actions
            for flag in action.option_strings
            if flag not in {"-h", "--help"}
        }
        assert flags <= set(re.findall(r"--[a-z][a-z-]*", document))

    ordered = [
        "$prepare-project-docs",
        "$start-backend",
        "$start-design",
        "$start-generatehtml",
        "$start-frontend",
        "$start-mobile",
        "$start-integration",
        "$start-testing",
        "$start-deployment",
        "$start-delivery",
    ]
    order_section = document.split(
        "For deliberate web/mobile stage-by-stage execution", 1
    )[1].split("Afterward,", 1)[0]
    positions = [order_section.index(name) for name in ordered]
    assert positions == sorted(positions)
    table_section = document.split("## All available skills", 1)[1].split(
        "## Project document preparation", 1
    )[0]
    table_names = re.findall(r"\| `\$([a-z-]+)` \|", table_section)
    assert table_names == catalog_names


def test_readme_has_zero_knowledge_codex_bootstrap() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    assert 'setup-workflow "https://github.com/Dolan001/agents.git"' in readme
    assert "not a terminal command, `$skill`, or installed" in readme
    assert "git submodule add -b dev" in readme
    assert "./.agents/bin/ai select-packs --project ." in readme
    assert "--recursive" not in readme
    assert "Refuse to overwrite an existing `.agents`" in readme
    assert "$start-build" in readme
    assert "$create-requirements" in readme
    assert (
        readme.index("$create-requirements")
        < readme.index("$generate-prd")
        < readme.index("$prepare-project-docs")
        < readme.index("$start-build")
    )


def test_requirements_intake_is_reviewed_before_document_generation() -> None:
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skills/create-requirements/SKILL.md").read_text()
    coverage = root / "skills/create-requirements/references/intake-coverage.md"
    agent = (root / "base/agents/requirements-intake-agent.md").read_text()
    assert "REQUIREMENTS.md" in skill
    assert coverage.is_file()
    assert "Pending user approval" in skill
    assert "explicitly approves" in skill
    assert "mark `Review status: Approved by user` and stop" in skill
    assert "Do not run either" in skill
    assert "Mark it approved only on explicit approval, then stop" in agent
