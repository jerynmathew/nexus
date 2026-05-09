from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SCORE = 0.5
_MIN_SCORE = 0.0
_MAX_SCORE = 1.0

_ACTION_PREFIXES = (
    "search_",
    "list_",
    "get_",
    "send_",
    "create_",
    "delete_",
    "manage_",
    "modify_",
    "query_",
    "draft_",
    "batch_",
    "start_",
)

_SERVICE_KEYWORDS = {
    "gmail": "gmail",
    "calendar": "calendar",
    "calendars": "calendar",
    "event": "calendar",
    "events": "calendar",
    "freebusy": "calendar",
    "task": "tasks",
    "tasks": "tasks",
    "drive": "drive",
    "doc": "docs",
    "sheet": "sheets",
    "search": "search",
    "web": "search",
}


def tool_category(tool_name: str) -> str:
    lower = tool_name.lower()
    for prefix in _ACTION_PREFIXES:
        if lower.startswith(prefix):
            lower = lower[len(prefix) :]
            break

    for keyword, category in _SERVICE_KEYWORDS.items():
        if keyword in lower:
            return category

    return "general"


class TrustStore:
    def __init__(self) -> None:
        self._scores: dict[str, dict[str, float]] = {}

    def get_score(self, tenant_id: str, category: str) -> float:
        return self._scores.get(tenant_id, {}).get(category, _DEFAULT_SCORE)

    def update_score(self, tenant_id: str, category: str, delta: float) -> float:
        tenant_scores = self._scores.setdefault(tenant_id, {})
        current = tenant_scores.get(category, _DEFAULT_SCORE)
        new_score = max(_MIN_SCORE, min(_MAX_SCORE, current + delta))
        tenant_scores[category] = new_score
        logger.info(
            "Trust updated: tenant=%s category=%s %.2f → %.2f (delta=%+.2f)",
            tenant_id,
            category,
            current,
            new_score,
            delta,
        )
        return new_score

    def get_all_scores(self, tenant_id: str) -> dict[str, float]:
        return dict(self._scores.get(tenant_id, {}))

    async def load_from_memory(self, ask_fn: Any, tenant_id: str) -> None:
        try:
            result = await ask_fn(
                "memory",
                {
                    "action": "config_get_all",
                    "tenant_id": f"_trust_{tenant_id}",
                },
            )
            configs = result.payload.get("configs", {})
            scores = configs.get("scores", {})
            if scores:
                self._scores[tenant_id] = {k: float(v) for k, v in scores.items()}
        except Exception:
            logger.debug("Failed to load trust scores for %s", tenant_id)

    async def save_to_memory(self, send_fn: Any, tenant_id: str) -> None:
        scores = self._scores.get(tenant_id, {})
        for category, score in scores.items():
            try:
                await send_fn(
                    "memory",
                    {
                        "action": "config_set",
                        "tenant_id": f"_trust_{tenant_id}",
                        "namespace": "scores",
                        "key": category,
                        "value": str(score),
                    },
                )
            except Exception:
                logger.debug("Failed to save trust score %s/%s", tenant_id, category)
