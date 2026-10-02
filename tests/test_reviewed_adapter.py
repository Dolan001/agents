import pytest

from ai_workflow.cli import parser


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["start-backend"], "codex-reviewed"),
        (["start-frontend"], "codex-reviewed"),
        (["start-generatehtml"], "codex-reviewed"),
        (["resume-build"], "codex-reviewed"),
        (["build"], "codex"),
        (["one-shot", "--prd", "PRD.md", "--backend", "django-drf"], "codex"),
        (["generate-prd", "--requirements", "REQUIREMENTS.md"], "codex"),
        (["prepare-project-docs"], "codex"),
        (["resolve-token", "--token", "example"], "codex"),
        (["sync-design"], "codex"),
    ],
)
def test_lifecycle_commands_default_to_reviewed_adapter(
    arguments: list[str], expected: str
) -> None:
    cli = parser()
    assert cli.parse_args(arguments).adapter == expected
    assert cli.parse_args([*arguments, "--adapter", "codex-reviewed"]).adapter == "codex-reviewed"
    assert cli.parse_args([*arguments, "--adapter", "codex"]).adapter == "codex"
    with pytest.raises(SystemExit):
        cli.parse_args([*arguments, "--adapter", "unrestricted"])
