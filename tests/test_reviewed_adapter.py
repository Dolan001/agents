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
    parsed = cli.parse_args(arguments)
    assert parsed.adapter is None
    assert parsed._codex_adapter_default == expected
    assert cli.parse_args([*arguments, "--adapter", "codex-reviewed"]).adapter == "codex-reviewed"
    assert cli.parse_args([*arguments, "--adapter", "codex"]).adapter == "codex"
    assert cli.parse_args([*arguments, "--adapter", "claude"]).adapter == "claude"
    assert cli.parse_args([*arguments, "--adapter", "opencode"]).adapter == "opencode"
    assert cli.parse_args([*arguments, "--adapter", "gemini"]).adapter == "gemini"
    assert cli.parse_args([*arguments, "--adapter", "cursor"]).adapter == "cursor"
    with pytest.raises(SystemExit):
        cli.parse_args([*arguments, "--adapter", "unrestricted"])


def test_backend_accepts_guarded_verification_only_mode() -> None:
    args = parser().parse_args(["start-backend", "--verification-only"])
    assert args.verification_only is True
