from __future__ import annotations

import pytest

from nexus.models.tenant import TenantContext


class TestTenantContext:
    def test_admin_has_all_permissions(self) -> None:
        tenant = TenantContext(tenant_id="t1", name="Admin", role="admin")
        assert tenant.has_permission("gmail", "read")
        assert tenant.has_permission("gmail", "write")
        assert tenant.has_permission("anything", "delete")

    def test_user_checks_permissions(self) -> None:
        tenant = TenantContext(
            tenant_id="t1",
            name="User",
            role="user",
            permissions={"gmail": ["read"], "calendar": ["read", "write"]},
        )
        assert tenant.has_permission("gmail", "read")
        assert not tenant.has_permission("gmail", "write")
        assert tenant.has_permission("calendar", "write")

    def test_no_permissions_for_unknown_service(self) -> None:
        tenant = TenantContext(
            tenant_id="t1", name="User", role="user", permissions={"gmail": ["read"]}
        )
        assert not tenant.has_permission("slack", "read")

    def test_check_action_permission(self) -> None:
        tenant = TenantContext(
            tenant_id="t1",
            name="User",
            role="user",
            permissions={"gmail": ["read"]},
        )
        assert tenant.check_action_permission("gmail", "search")
        assert not tenant.check_action_permission("gmail", "send")
        assert not tenant.check_action_permission("gmail", "delete")

    def test_frozen(self) -> None:
        tenant = TenantContext(tenant_id="t1", name="User")
        with pytest.raises(ValueError):
            tenant.name = "Changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        tenant = TenantContext(tenant_id="t1", name="User")
        assert tenant.role == "user"
        assert tenant.persona_name == "default"
        assert tenant.timezone == "UTC"
        assert tenant.permissions == {}
