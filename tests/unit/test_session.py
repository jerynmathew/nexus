from __future__ import annotations

from nexus.models.session import Session


class TestSession:
    def test_serialization_roundtrip(self) -> None:
        session = Session(session_id="s1", tenant_id="t1")
        session.add_message("user", "hello")
        session.add_message("assistant", "hi there")

        data = session.to_dict()
        restored = Session.from_dict(data)

        assert restored.session_id == "s1"
        assert restored.tenant_id == "t1"
        assert len(restored.messages) == 2
        assert restored.messages[0]["role"] == "user"
        assert restored.messages[1]["content"] == "hi there"

    def test_add_message_updates_activity(self) -> None:
        session = Session(session_id="s1", tenant_id="t1")
        initial = session.last_activity
        session.add_message("user", "test")
        assert session.last_activity >= initial

    def test_add_message_with_kwargs(self) -> None:
        session = Session(session_id="s1", tenant_id="t1")
        session.add_message("assistant", "response", tool_calls=[{"id": "tc1"}])
        assert session.messages[0]["tool_calls"] == [{"id": "tc1"}]

    def test_default_status(self) -> None:
        session = Session(session_id="s1", tenant_id="t1")
        assert session.status == "active"

    def test_from_dict_defaults(self) -> None:
        data = {"session_id": "s1", "tenant_id": "t1"}
        session = Session.from_dict(data)
        assert session.status == "active"
        assert session.messages == []
