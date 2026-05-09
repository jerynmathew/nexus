from __future__ import annotations

from pathlib import Path

from nexus.persona.loader import PersonaLoader


def _setup_personas(tmp_path: Path) -> tuple[Path, Path]:
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    (personas_dir / "default.md").write_text("# Default\nYou are helpful.")
    (personas_dir / "dross.md").write_text("# Dross\nYou are witty.")
    return personas_dir, users_dir


class TestPersonaLoader:
    def test_load_existing_persona(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        content = loader.load_persona("dross")
        assert "Dross" in content
        assert "witty" in content

    def test_fallback_to_default(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        content = loader.load_persona("nonexistent")
        assert "Default" in content

    def test_cache_hit(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        first = loader.load_persona("dross")
        (personas_dir / "dross.md").write_text("# Changed\nDifferent.")
        second = loader.load_persona("dross")
        assert first == second

    def test_cache_invalidation(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        loader.load_persona("dross")
        loader.invalidate_cache("dross")
        (personas_dir / "dross.md").write_text("# Changed\nDifferent.")
        content = loader.load_persona("dross")
        assert "Changed" in content

    def test_user_context_exists(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        tenant_dir = users_dir / "jeryn"
        tenant_dir.mkdir()
        (tenant_dir / "USER.md").write_text("# Jeryn\n- Vegetarian")
        loader = PersonaLoader(personas_dir, users_dir)
        ctx = loader.load_user_context("jeryn")
        assert ctx is not None
        assert "Vegetarian" in ctx

    def test_user_context_missing(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        ctx = loader.load_user_context("nonexistent")
        assert ctx is None

    def test_build_system_identity(self, tmp_path: Path) -> None:
        personas_dir, users_dir = _setup_personas(tmp_path)
        loader = PersonaLoader(personas_dir, users_dir)
        identity = loader.build_system_identity(
            persona_name="dross",
            tenant_id="jeryn",
            tenant_name="Jeryn",
            timezone="UTC",
            role="admin",
        )
        assert "Dross" in identity
        assert "Jeryn" in identity
        assert "admin" in identity

    def test_missing_both_personas(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        loader = PersonaLoader(empty_dir, users_dir)
        content = loader.load_persona("anything")
        assert "Nexus" in content
