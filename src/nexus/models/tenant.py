from __future__ import annotations

from pydantic import BaseModel, ConfigDict

WRITE_ACTIONS = frozenset({"create", "send", "delete", "update", "write"})


class TenantProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = "default"
    persona_name: str = "default"


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    name: str
    role: str = "user"
    persona_name: str = "default"
    active_profile: str = "default"
    profiles: dict[str, TenantProfile] = {}
    timezone: str = "UTC"
    permissions: dict[str, list[str]] = {}

    def persona_for_profile(self, profile: str | None = None) -> str:
        profile = profile or self.active_profile
        if profile in self.profiles:
            return self.profiles[profile].persona_name
        return self.persona_name

    def has_permission(self, service: str, level: str) -> bool:
        if self.role == "admin":
            return True
        allowed = self.permissions.get(service, [])
        return level in allowed

    def check_action_permission(self, service: str, action: str) -> bool:
        level = "write" if action in WRITE_ACTIONS else "read"
        return self.has_permission(service, level)
