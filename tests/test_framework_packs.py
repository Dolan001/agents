import json
from pathlib import Path

from ai_workflow.execution import _agent_path, _control_paths, _skill_paths

PACK_NAMES = ("django-drf", "fastapi", "flutter", "nextjs", "react")
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
        assert agents["format"] == "markdown-first"
        assert skills["format"] == "markdown-first"
        assert structure["framework"] == name
        assert structure["target_root"] == specification["target"]
        assert agents["agents"]
        assert skills["skills"]
        for agent in agents["agents"]:
            assert (pack / "agents" / f"{agent['agent']}.md").is_file()
        for skill in skills["skills"]:
            skill_path = pack / skill["path"]
            assert skill_path.is_file()
            assert skill_path.name == "SKILL.md"
        assert structure["required_paths"]
        assert "required_directories" in structure
        assert set(structure.get("required_directories", [])) <= set(structure["required_paths"])
        assert (pack / "rules" / "project-structure.md").is_file()
        lifecycle = json.loads((pack / "hooks" / "lifecycle.json").read_text())
        assert "validate_generated_structure" in lifecycle["hooks"]["post_write"]
        for instruction in lifecycle["instructions"].values():
            assert (pack / instruction).is_file()


def test_framework_packs_have_production_roles_and_progressive_references() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config" / "framework-packs.json").read_text())

    for name, specification in config["packs"].items():
        pack = root / specification["path"]
        agents = json.loads((pack / "agents" / "catalog.json").read_text())["agents"]
        agent_names = {agent["agent"] for agent in agents}
        assert len(agents) == 3, name
        assert any(agent.endswith("-solution-architect") for agent in agent_names), name
        assert any(agent.endswith("-implementer") for agent in agent_names), name
        assert any(agent.endswith("-independent-verifier") for agent in agent_names), name

        references = list(pack.glob("skills/implement-*/references/production-delivery.md"))
        assert len(references) == 1, name
        reference = references[0].read_text().lower()
        for concern in ("security", "verification", "error", "test"):
            assert concern in reference, f"{name} lacks {concern} production guidance"


def test_framework_nodes_route_only_role_specific_skills_rules_hooks_and_agents() -> None:
    root = Path(__file__).resolve().parents[1]
    cases = (
        ("frontend", "react", "react_ai"),
        ("frontend", "nextjs", "nextjs_ai"),
        ("mobile", "flutter", "flutter_ai"),
        ("backend", "django-drf", "drf_ai"),
        ("backend", "fastapi", "fastapi_ai"),
    )
    for phase, framework, pack_name in cases:
        frameworks = {"frontend": "unknown", "mobile": "unknown", "backend": "unknown"}
        frameworks[phase] = framework
        pack = root / pack_name

        implementer = _agent_path(root, f"selected-{phase}-agent", frameworks)
        verifier = _agent_path(root, f"selected-{phase}-verifier", frameworks)
        assert implementer.parent == pack / "agents"
        assert implementer.name.endswith("-implementer.md")
        assert verifier.parent == pack / "agents"
        assert verifier.name.endswith("-independent-verifier.md")

        implement_node = f"implement-{phase}-slices"
        framework_skills = [
            path
            for path in _skill_paths(root, phase, implement_node, frameworks)
            if pack in path.parents
        ]
        expected = 2 if phase == "backend" else 1
        assert len(framework_skills) == expected
        assert any(path.parent.name.startswith("implement-") for path in framework_skills)
        if phase == "backend":
            assert any(path.parent.name.startswith("create-") for path in framework_skills)

        verify_skills = [
            path
            for path in _skill_paths(root, phase, f"verify-{phase}", frameworks)
            if pack in path.parents
        ]
        assert len(verify_skills) == 1
        assert verify_skills[0].parent.name.startswith("verify-")
        all_verify_skills = _skill_paths(root, phase, f"verify-{phase}", frameworks)
        assert any(path.parent.name == "verify-feature" for path in all_verify_skills)
        assert not any(path.parent.name == "execute-task-contract" for path in all_verify_skills)

        implement_controls = _control_paths(root, phase, implement_node, frameworks)
        assert pack / "rules" / "architecture.md" in implement_controls
        assert pack / "rules" / "generation.md" in implement_controls
        assert pack / "hooks" / "pre-write.md" in implement_controls
        verify_controls = _control_paths(root, phase, f"verify-{phase}", frameworks)
        assert pack / "rules" / "verification.md" in verify_controls
        assert pack / "hooks" / "pre-verify.md" in verify_controls


def test_backend_packs_require_postgresql_domains_and_database_api_guidance() -> None:
    root = Path(__file__).resolve().parents[1]
    for pack_name in ("drf_ai", "fastapi_ai"):
        pack = root / pack_name
        structure = json.loads((pack / "rules" / "project-structure.json").read_text())
        assert structure["minimum_domain_instances"] == 1
        assert structure["required_domain_paths"]
        assert structure["required_domain_directories"]
        forbidden = " ".join(structure["forbidden_patterns"]).lower()
        assert "sqlite" in forbidden
        assert "migration" in forbidden or "create_all" in forbidden

        references = list(pack.glob("skills/implement-*/references/database-api-architecture.md"))
        assert len(references) == 1
        guidance = references[0].read_text().lower()
        for concern in (
            "postgresql",
            "migration",
            "constraint",
            "index",
            "query",
            "serializer" if pack_name == "drf_ai" else "schema",
            "url" if pack_name == "drf_ai" else "router",
        ):
            assert concern in guidance, f"{pack_name} lacks {concern} guidance"
