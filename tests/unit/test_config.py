from __future__ import annotations

from pathlib import Path

import pytest

from nexus.config import NexusConfig, load_config


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


class TestLoadConfig:
    def test_valid_minimal(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "llm:\n  model: test-model\n")
        cfg = load_config(path)
        assert cfg.llm.model == "test-model"
        assert cfg.llm.base_url == "http://localhost:4000"

    def test_defaults_applied(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "{}\n")
        cfg = load_config(path)
        assert cfg.llm.model == "claude-sonnet-4-20250514"
        assert cfg.memory.db_path == "data/nexus.db"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_unknown_keys_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "bogus_key: true\n")
        with pytest.raises(ValueError, match="Unknown config keys"):
            load_config(path)

    def test_env_var_substitution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_BOT_TOKEN", "my-secret-token")
        path = _write_yaml(
            tmp_path,
            "telegram:\n  bot_token: ${TEST_BOT_TOKEN}\n",
        )
        cfg = load_config(path)
        assert cfg.telegram is not None
        assert cfg.telegram.bot_token == "my-secret-token"

    def test_seed_users_parsed(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            (
                "seed_users:\n"
                "  - name: Alice\n"
                "    tenant_id: alice\n"
                "    role: admin\n"
                "    persona: dross\n"
                "    timezone: Asia/Kolkata\n"
                "    telegram_user_id: 12345\n"
            ),
        )
        cfg = load_config(path)
        assert len(cfg.seed_users) == 1
        assert cfg.seed_users[0].name == "Alice"
        assert cfg.seed_users[0].telegram_user_id == 12345

    def test_path_resolution_relative(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "persona_dir: my_personas\n")
        cfg = load_config(path)
        assert cfg.persona_dir == str(tmp_path / "my_personas")

    def test_empty_file(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "")
        cfg = load_config(path)
        assert isinstance(cfg, NexusConfig)

    def test_seed_users_none(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "seed_users: null\n")
        cfg = load_config(path)
        assert cfg.seed_users == []
