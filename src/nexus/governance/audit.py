from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    agent: str = ""
    tenant_id: str = ""
    tool_name: str = ""
    arguments_summary: str = ""
    decision: str = ""
    detail: str = ""


class AuditSink:
    def __init__(self, path: str = "data/audit.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        try:
            line = json.dumps(asdict(entry), ensure_ascii=False)
            with self._path.open("a") as f:
                f.write(line + "\n")
        except Exception:
            logger.warning("Failed to write audit entry", exc_info=True)

    @staticmethod
    def summarize_arguments(arguments: dict[str, Any]) -> str:
        keys = list(arguments.keys())[:5]
        return ", ".join(f"{k}=..." for k in keys) if keys else "(none)"
