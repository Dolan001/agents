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
        **{name: name for name in skill_names if name != "workflow-status"},
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
        "$generate-prd",
        "$start-design",
        "$start-generatehtml",
        "$start-frontend",
        "$start-mobile",
        "$start-backend",
        "$start-integration",
        "$start-testing",
        "$start-deployment",
        "$start-delivery",
    ]
    order_section = document.split("For deliberate stage-by-stage execution", 1)[1].split(
        "Afterward,", 1
    )[0]
    positions = [order_section.index(name) for name in ordered]
    assert positions == sorted(positions)
    table_section = document.split("## All available skills", 1)[1].split(
        "## PRD generation", 1
    )[0]
    table_names = re.findall(r"\| `\$([a-z-]+)` \|", table_section)
    assert table_names == catalog_names


def test_readme_has_zero_knowledge_codex_bootstrap() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    assert 'setup-workflow "https://github.com/Dolan001/agents.git"' in readme
    assert "not a terminal command, `$skill`, or installed" in readme
    assert "git submodule add -b dev" in readme
    assert "git submodule update --init --recursive" in readme
    assert "Refuse to overwrite an existing `.agents`" in readme
    assert "$start-build" in readme
