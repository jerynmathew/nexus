from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_PATTERN = re.compile(r"^###\s+(.+)$", re.MULTILINE)


@dataclass
class SkillSection:
    name: str
    content: str
    timeout: int = 30


@dataclass
class Skill:
    name: str
    description: str = ""
    execution: str = "sequential"
    tool_groups: list[str] = field(default_factory=list)
    schedule: str | None = None
    timeout_per_section: int = 30
    active_hours_only: bool = False
    sections: list[SkillSection] = field(default_factory=list)
    content: str = ""
    source_path: Path | None = None


def parse_skill(path: Path) -> Skill:
    raw = path.read_text()
    meta: dict[str, Any] = {}
    body = raw

    fm_match = _FRONTMATTER_PATTERN.match(raw)
    if fm_match:
        meta = yaml.safe_load(fm_match.group(1)) or {}
        body = raw[fm_match.end() :]

    if "name" not in meta:
        raise ValueError(f"SKILL.md missing required 'name' in frontmatter: {path}")

    timeout = meta.get("timeout_per_section", 30)
    sections = _parse_sections(body, timeout)

    return Skill(
        name=meta["name"],
        description=meta.get("description", ""),
        execution=meta.get("execution", "sequential"),
        tool_groups=meta.get("tool_groups", []),
        schedule=meta.get("schedule"),
        timeout_per_section=timeout,
        active_hours_only=bool(meta.get("active_hours_only", False)),
        sections=sections,
        content=body.strip(),
        source_path=path,
    )


def _parse_sections(body: str, default_timeout: int) -> list[SkillSection]:
    matches = list(_SECTION_PATTERN.finditer(body))
    if not matches:
        return []

    sections: list[SkillSection] = []
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections.append(SkillSection(name=name, content=content, timeout=default_timeout))

    return sections
