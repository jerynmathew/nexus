from __future__ import annotations

from pathlib import Path

from nexus.skills.manager import SkillManager


def _create_skill(skills_dir: Path, name: str, schedule: str | None = None) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    sched_line = f'schedule: "{schedule}"\n' if schedule else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} skill\n{sched_line}---\n\nContent.\n",
    )


class TestSkillManager:
    def test_load_all(self, tmp_path: Path) -> None:
        _create_skill(tmp_path, "skill-a")
        _create_skill(tmp_path, "skill-b")
        manager = SkillManager(tmp_path)
        manager.load_all()
        assert len(manager.list_skills()) == 2

    def test_get_by_name(self, tmp_path: Path) -> None:
        _create_skill(tmp_path, "test-skill")
        manager = SkillManager(tmp_path)
        skill = manager.get("test-skill")
        assert skill is not None
        assert skill.name == "test-skill"

    def test_get_missing(self, tmp_path: Path) -> None:
        manager = SkillManager(tmp_path)
        assert manager.get("nonexistent") is None

    def test_get_scheduled(self, tmp_path: Path) -> None:
        _create_skill(tmp_path, "cron-skill", schedule="0 7 * * *")
        _create_skill(tmp_path, "no-cron")
        manager = SkillManager(tmp_path)
        scheduled = manager.get_scheduled()
        assert len(scheduled) == 1
        assert scheduled[0].name == "cron-skill"

    def test_build_summary(self, tmp_path: Path) -> None:
        _create_skill(tmp_path, "my-skill")
        manager = SkillManager(tmp_path)
        summary = manager.build_summary()
        assert "my-skill" in summary

    def test_empty_dir(self, tmp_path: Path) -> None:
        manager = SkillManager(tmp_path / "nonexistent")
        assert manager.list_skills() == []

    def test_lazy_load(self, tmp_path: Path) -> None:
        _create_skill(tmp_path, "lazy")
        manager = SkillManager(tmp_path)
        assert manager.get("lazy") is not None
