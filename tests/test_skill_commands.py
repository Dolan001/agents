import argparse
import json
import re
from pathlib import Path

from ai_workflow.cli import parser


def test_skill_command_reference_covers_catalog_and_cli_flags() -> None:
    root = Path(__file__).resolve().parents[1]
    document = (root / "SKILL_COMMANDS.md").read_text()
    catalog = json.loads((root / "skills" / "catalog.json").read_text())
    skill_names = {item["name"] for item in catalog["skills"]}
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
