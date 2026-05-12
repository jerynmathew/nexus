from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.models.profile import UserProfile


class TestUserProfile:
    def test_all_fields(self) -> None:
        p = UserProfile(
            tenant_id="t1",
            name="Alice",
            email="a@b.com",
            timezone="Asia/Kolkata",
            persona_name="dross",
        )
        assert p.tenant_id == "t1"
        assert p.email == "a@b.com"
        assert p.persona_name == "dross"

    def test_defaults(self) -> None:
        p = UserProfile(tenant_id="t1", name="Bob")
        assert p.email is None
        assert p.timezone == "UTC"
        assert p.persona_name == "default"

    def test_frozen(self) -> None:
        p = UserProfile(tenant_id="t1", name="Alice")
        with pytest.raises(ValidationError):
            p.name = "Bob"
