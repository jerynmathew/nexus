from __future__ import annotations

from enum import Enum
from typing import Any

_READ_PREFIXES = ("search_", "list_", "get_", "query_", "read_", "fetch_", "find_")
_WRITE_PREFIXES = ("send_", "create_", "delete_", "update_", "modify_", "remove_", "manage_")


class PolicyDecision(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


_TRUST_AUTONOMOUS = 0.8
_TRUST_ADVISORY_ONLY = 0.5


class PolicyEngine:
    def __init__(
        self,
        deny_patterns: list[str] | None = None,
        autonomous_threshold: float = _TRUST_AUTONOMOUS,
        advisory_threshold: float = _TRUST_ADVISORY_ONLY,
    ) -> None:
        self._deny_patterns = deny_patterns or []
        self._autonomous_threshold = autonomous_threshold
        self._advisory_threshold = advisory_threshold

    def check(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        trust_score: float | None = None,
    ) -> PolicyDecision:
        for pattern in self._deny_patterns:
            if pattern in tool_name:
                return PolicyDecision.DENY

        lower = tool_name.lower()

        if any(lower.startswith(prefix) for prefix in _READ_PREFIXES):
            return PolicyDecision.ALLOW

        if any(lower.startswith(prefix) for prefix in _WRITE_PREFIXES):
            return self._check_with_trust(trust_score)

        return PolicyDecision.ALLOW

    def _check_with_trust(self, trust_score: float | None) -> PolicyDecision:
        if trust_score is None:
            return PolicyDecision.REQUIRE_APPROVAL
        if trust_score >= self._autonomous_threshold:
            return PolicyDecision.ALLOW
        if trust_score < self._advisory_threshold:
            return PolicyDecision.DENY
        return PolicyDecision.REQUIRE_APPROVAL
