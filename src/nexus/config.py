from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _substitute_env_vars(data: Any) -> Any:
    if isinstance(data, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(0)), data)
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    return data


_KNOWN_TOP_LEVEL_KEYS = frozenset(
    {
        "llm",
        "telegram",
        "memory",
        "seed_users",
        "persona_dir",
        "users_dir",
        "data_dir",
    }
)


class LLMConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = "http://localhost:4000"
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class TelegramConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    bot_token: str
    allowed_user_ids: list[int] = []


class MemoryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    db_path: str = "data/nexus.db"


class TenantSeedUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    tenant_id: str
    role: str = "admin"
    persona: str = "default"
    timezone: str = "UTC"
    telegram_user_id: int | None = None


class NexusConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    llm: LLMConfig = LLMConfig()
    telegram: TelegramConfig | None = None
    memory: MemoryConfig = MemoryConfig()
    seed_users: list[TenantSeedUser] = []
    persona_dir: str = "personas"
    users_dir: str = "data/users"
    data_dir: str = "data"

    @field_validator("seed_users", mode="before")
    @classmethod
    def _default_seed_users(cls, v: Any) -> Any:
        if v is None:
            return []
        return v


def load_config(path: Path) -> NexusConfig:
    """Load and validate NexusConfig from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raw = {}

    raw = _substitute_env_vars(raw)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

    unknown = set(raw.keys()) - _KNOWN_TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(f"Unknown config keys: {unknown!r}")

    config_dir = path.parent.resolve()

    for key in ("persona_dir", "users_dir", "data_dir"):
        if key in raw and not Path(raw[key]).is_absolute():
            raw[key] = str(config_dir / raw[key])

    if "memory" in raw and "db_path" in raw["memory"]:
        db_path = Path(raw["memory"]["db_path"])
        if not db_path.is_absolute():
            raw["memory"]["db_path"] = str(config_dir / db_path)

    return NexusConfig.model_validate(raw)
