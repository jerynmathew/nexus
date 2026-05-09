from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class PersonaLoader:
    def __init__(self, personas_dir: Path, users_dir: Path) -> None:
        self._personas_dir = personas_dir
        self._users_dir = users_dir
        self._cache: dict[str, str] = {}

    def load_persona(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]

        path = self._personas_dir / f"{name}.md"
        if not path.exists():
            logger.warning("Persona '%s' not found, falling back to default", name)
            path = self._personas_dir / "default.md"

        if not path.exists():
            logger.warning("Default persona not found at %s", path)
            return "You are Nexus, a helpful personal AI assistant."

        content = path.read_text()
        self._cache[name] = content
        return content

    def load_user_context(self, tenant_id: str) -> str | None:
        path = self._users_dir / tenant_id / "USER.md"
        if path.exists():
            return path.read_text()
        return None

    def build_system_identity(
        self,
        persona_name: str,
        tenant_id: str,
        tenant_name: str,
        timezone: str,
        role: str = "user",
    ) -> str:
        parts: list[str] = []

        parts.append(self.load_persona(persona_name))

        user_md = self.load_user_context(tenant_id)
        if user_md:
            parts.append(f"# About {tenant_name}\n\n{user_md}")

        now = datetime.now(tz=ZoneInfo(timezone))
        runtime_ctx = (
            f"Current time: {now.strftime('%A, %B %d, %Y %I:%M %p %Z')}\n"
            f"User: {tenant_name} (role: {role})\n"
            f"Timezone: {timezone}"
        )
        parts.append(runtime_ctx)

        return "\n\n---\n\n".join(parts)

    def invalidate_cache(self, name: str | None = None) -> None:
        if name is None:
            self._cache.clear()
        else:
            self._cache.pop(name, None)
