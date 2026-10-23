from pathlib import Path


def test_lifecycle_skills_share_start_command_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    lifecycle_skills = sorted((root / "skills").glob("start-*/SKILL.md"))
    lifecycle_skills.append(root / "skills/resume-build/SKILL.md")

    assert lifecycle_skills
    for skill in lifecycle_skills:
        assert "commands/references/start-command-contract.md" in skill.read_text(), skill


def test_status_skill_identifies_recorded_issues_as_historical() -> None:
    root = Path(__file__).resolve().parents[1]
    status_skill = (root / "skills/workflow-status/SKILL.md").read_text()
    assert "not current adapter quota" in status_skill
