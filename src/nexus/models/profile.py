from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    name: str
    email: str | None = None
    timezone: str = "UTC"
    persona_name: str = "default"
