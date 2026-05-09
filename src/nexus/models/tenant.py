from __future__ import annotations

from pydantic import BaseModel, ConfigDict

WRITE_ACTIONS = frozenset({"create", "send", "delete", "update", "write"})


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    name: str
    role: str = "user"
    persona_name: str = "default"
    timezone: str = "UTC"
    permissions: dict[str, list[str]] = {}

    def has_permission(self, service: str, level: str) -> bool:
        if self.role == "admin":
            return True
        allowed = self.permissions.get(service, [])
        return level in allowed

    def check_action_permission(self, service: str, action: str) -> bool:
        level = "write" if action in WRITE_ACTIONS else "read"
        return self.has_permission(service, level)
