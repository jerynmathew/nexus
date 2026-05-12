from __future__ import annotations

import logging
from pathlib import Path

from nexus.skills.parser import Skill, parse_skill

logger = logging.getLogger(__name__)


class SkillManager:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir
        self._extra_dirs: list[Path] = []
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def add_skill_dir(self, path: Path) -> None:
        if path not in self._extra_dirs:
            self._extra_dirs.append(path)
            if self._loaded:
                self._load_from_dir(path)

    def load_all(self) -> None:
        self._skills.clear()
        self._load_from_dir(self._skills_dir)
        for extra in self._extra_dirs:
            self._load_from_dir(extra)
        self._loaded = True

    def _load_from_dir(self, directory: Path) -> None:
        if not directory.exists():
            logger.info("Skills directory does not exist: %s", directory)
            return

        for skill_dir in sorted(directory.iterdir()):
            skill_file = skill_dir / "SKILL.md" if skill_dir.is_dir() else None
            if skill_file is None or not skill_file.exists():
                if skill_dir.suffix == ".md" and skill_dir.is_file():
                    skill_file = skill_dir
                else:
                    continue

            try:
                skill = parse_skill(skill_file)
                self._skills[skill.name] = skill
                logger.info("Loaded skill: %s", skill.name)
            except Exception:
                logger.warning("Failed to load skill from %s", skill_file, exc_info=True)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_all()

    def get(self, name: str) -> Skill | None:
        self._ensure_loaded()
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        self._ensure_loaded()
        return list(self._skills.values())

    def get_scheduled(self) -> list[Skill]:
        self._ensure_loaded()
        return [s for s in self._skills.values() if s.schedule]

    def build_summary(self) -> str:
        self._ensure_loaded()
        if not self._skills:
            return ""
        lines = [f"- **{s.name}**: {s.description}" for s in self._skills.values()]
        return "\n".join(lines)
