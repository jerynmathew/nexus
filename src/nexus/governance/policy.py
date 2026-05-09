from __future__ import annotations

from enum import Enum
from typing import Any

_READ_PREFIXES = ("search_", "list_", "get_", "query_", "read_", "fetch_", "find_")
_WRITE_PREFIXES = ("send_", "create_", "delete_", "update_", "modify_", "remove_", "manage_")


class PolicyDecision(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class PolicyEngine:
    def __init__(self, deny_patterns: list[str] | None = None) -> None:
        self._deny_patterns = deny_patterns or []

    def check(self, tool_name: str, arguments: dict[str, Any] | None = None) -> PolicyDecision:
        for pattern in self._deny_patterns:
            if pattern in tool_name:
                return PolicyDecision.DENY

        lower = tool_name.lower()

        if any(lower.startswith(prefix) for prefix in _READ_PREFIXES):
            return PolicyDecision.ALLOW

        if any(lower.startswith(prefix) for prefix in _WRITE_PREFIXES):
            return PolicyDecision.REQUIRE_APPROVAL

        return PolicyDecision.ALLOW
