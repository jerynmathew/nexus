from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_id: str
    tenant_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    status: str = "active"
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "messages": self.messages,
            "status": self.status,
            "started_at": self.started_at,
            "last_activity": self.last_activity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            session_id=data["session_id"],
            tenant_id=data["tenant_id"],
            messages=data.get("messages", []),
            status=data.get("status", "active"),
            started_at=data.get("started_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
        )

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        msg: dict[str, Any] = {"role": role, "content": content}
        if kwargs:
            msg.update(kwargs)
        self.messages.append(msg)
        self.last_activity = time.time()
