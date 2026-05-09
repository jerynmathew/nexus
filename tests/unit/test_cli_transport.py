from __future__ import annotations

from unittest.mock import AsyncMock

from nexus.transport.cli import CLITransport


class TestCLITransport:
    def test_transport_name(self):
        t = CLITransport(conversation_manager_send=AsyncMock())
        assert t.transport_name == "cli"

    async def test_send_text(self, capsys):
        t = CLITransport(conversation_manager_send=AsyncMock())
        await t.send_text("cli", "Hello from Nexus")
        captured = capsys.readouterr()
        assert "Hello from Nexus" in captured.out

    async def test_send_buttons(self, capsys):
        from nexus.transport.base import Button

        t = CLITransport(conversation_manager_send=AsyncMock())
        await t.send_buttons(
            "cli",
            "Choose:",
            [Button(label="Yes", callback_data="yes"), Button(label="No", callback_data="no")],
        )
        captured = capsys.readouterr()
        assert "Choose:" in captured.out
        assert "Yes" in captured.out
        assert "No" in captured.out

    async def test_send_typing_noop(self):
        t = CLITransport(conversation_manager_send=AsyncMock())
        await t.send_typing("cli")
