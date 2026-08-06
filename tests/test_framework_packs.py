import json
from pathlib import Path

PACK_NAMES = ("django-drf", "fastapi", "nextjs", "react")
REQUIRED_DIRECTORIES = {"agents", "skills", "commands", "hooks", "rules"}
ALLOWED_TOP_LEVEL = REQUIRED_DIRECTORIES | {"AGENTS.md", "README.md", ".git", ".gitignore"}
FORBIDDEN_APPLICATION_FILES = {
    "Dockerfile",
    "manage.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "docker-compose.yml",
}
FORBIDDEN_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html"}


def test_framework_packs_are_code_free_behavior_only() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config" / "framework-packs.json").read_text())
    assert config["copy_application_source"] is False
    assert set(config["packs"]) == set(PACK_NAMES)

    for name, specification in config["packs"].items():
        pack = (root / specification["path"]).resolve()
        assert pack.is_dir(), name
        entries = {entry.name for entry in pack.iterdir()}
        assert REQUIRED_DIRECTORIES <= entries
        assert entries <= ALLOWED_TOP_LEVEL

        files = [path for path in pack.rglob("*") if path.is_file() and ".git" not in path.parts]
        assert not ({path.name for path in files} & FORBIDDEN_APPLICATION_FILES)
        assert not [path for path in files if path.suffix in FORBIDDEN_SUFFIXES]

        agents = json.loads((pack / "agents" / "catalog.json").read_text())
        skills = json.loads((pack / "skills" / "catalog.json").read_text())
        structure = json.loads((pack / "rules" / "project-structure.json").read_text())
        assert agents["framework"] == name
        assert skills["framework"] == name
        assert structure["framework"] == name
        assert structure["target_root"] == specification["target"]
        assert agents["agents"]
        assert skills["skills"]
        assert structure["required_paths"]
        assert (pack / "rules" / "project-structure.md").is_file()
        assert "validate_generated_structure" in json.loads(
            (pack / "hooks" / "lifecycle.json").read_text()
        )["hooks"]["post_write"]
