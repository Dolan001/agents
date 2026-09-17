import pytest

from ai_workflow.cli import parser


@pytest.mark.parametrize(
    "arguments",
    [
        ["start-frontend"],
        ["start-generatehtml"],
        ["resume-build"],
        ["build"],
        ["one-shot", "--prd", "PRD.md", "--backend", "django-drf"],
        ["generate-prd", "--requirements", "REQUIREMENTS.md"],
        ["prepare-project-docs"],
        ["resolve-token", "--token", "example"],
        ["sync-design"],
    ],
)
def test_reviewed_adapter_requires_explicit_selection(arguments: list[str]) -> None:
    cli = parser()
    assert cli.parse_args(arguments).adapter == "codex"
    assert cli.parse_args([*arguments, "--adapter", "codex-reviewed"]).adapter == "codex-reviewed"
    with pytest.raises(SystemExit):
        cli.parse_args([*arguments, "--adapter", "unrestricted"])
