from __future__ import annotations

from pathlib import Path

import pytest

from nexus.skills.parser import parse_skill


def _write_skill(tmp_path: Path, content: str) -> Path:
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    path.write_text(content)
    return path


class TestParseSkill:
    def test_full_skill(self, tmp_path: Path) -> None:
        path = _write_skill(
            tmp_path,
            "---\n"
            "name: test-skill\n"
            "description: A test skill\n"
            "execution: parallel\n"
            "timeout_per_section: 20\n"
            "tool_groups: [gmail, calendar]\n"
            'schedule: "0 7 * * *"\n'
            "---\n"
            "\n"
            "# Test Skill\n"
            "\n"
            "## Sections\n"
            "\n"
            "### Email\n"
            "Fetch emails.\n"
            "\n"
            "### Calendar\n"
            "Fetch events.\n",
        )
        skill = parse_skill(path)
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.execution == "parallel"
        assert skill.tool_groups == ["gmail", "calendar"]
        assert skill.schedule == "0 7 * * *"
        assert len(skill.sections) == 2
        assert skill.sections[0].name == "Email"
        assert skill.sections[1].name == "Calendar"
        assert skill.sections[0].timeout == 20

    def test_sequential_skill(self, tmp_path: Path) -> None:
        path = _write_skill(
            tmp_path,
            "---\nname: simple\ndescription: Simple skill\n---\n\nDo something.\n",
        )
        skill = parse_skill(path)
        assert skill.name == "simple"
        assert skill.execution == "sequential"
        assert skill.sections == []
        assert "Do something" in skill.content

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        path = _write_skill(
            tmp_path,
            "---\ndescription: No name\n---\n\nContent.\n",
        )
        with pytest.raises(ValueError, match="missing required 'name'"):
            parse_skill(path)

    def test_defaults(self, tmp_path: Path) -> None:
        path = _write_skill(
            tmp_path,
            "---\nname: minimal\n---\n\nContent.\n",
        )
        skill = parse_skill(path)
        assert skill.execution == "sequential"
        assert skill.tool_groups == []
        assert skill.schedule is None
        assert skill.timeout_per_section == 30
