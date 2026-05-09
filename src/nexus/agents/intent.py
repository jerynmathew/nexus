from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from nexus.models.tenant import TenantContext


class Intent(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_service: str | None = None
    action: str | None = None
    skill_name: str | None = None
    is_stateful: bool = False
    is_skill_request: bool = False
    tool_groups: list[str] = []
    confidence: float = 1.0
    original_text: str = ""


@runtime_checkable
class IntentClassifier(Protocol):
    async def classify(self, text: str, tenant: TenantContext) -> Intent: ...


_EMAIL_PATTERNS = re.compile(
    r"\b(email|mail|inbox|gmail|unread|send\s+(?:a\s+)?(?:mail|email|message))\b",
    re.IGNORECASE,
)
_CALENDAR_PATTERNS = re.compile(
    r"\b(calendar|schedule|meeting|event|appointment|agenda|what.s\s+on)\b",
    re.IGNORECASE,
)
_TASK_PATTERNS = re.compile(
    r"\b(task|todo|reminder|to-do|pending)\b",
    re.IGNORECASE,
)


class RegexClassifier:
    async def classify(self, text: str, tenant: TenantContext) -> Intent:
        if _EMAIL_PATTERNS.search(text):
            write_keywords = re.search(
                r"\b(send|draft|reply|forward|compose|write)\b",
                text,
                re.IGNORECASE,
            )
            return Intent(
                target_service="gmail",
                action="write" if write_keywords else "read",
                tool_groups=["gmail"],
                confidence=0.8,
                original_text=text,
            )

        if _CALENDAR_PATTERNS.search(text):
            write_keywords = re.search(
                r"\b(create|book|schedule|cancel|accept|decline)\b",
                text,
                re.IGNORECASE,
            )
            return Intent(
                target_service="calendar",
                action="write" if write_keywords else "read",
                tool_groups=["calendar"],
                confidence=0.8,
                original_text=text,
            )

        if _TASK_PATTERNS.search(text):
            return Intent(
                target_service="tasks",
                action="read",
                tool_groups=["tasks"],
                confidence=0.7,
                original_text=text,
            )

        return Intent(
            confidence=0.5,
            original_text=text,
        )
