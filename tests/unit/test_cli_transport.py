from __future__ import annotations

import asyncio
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

    async def test_start_creates_task(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn)
        from unittest.mock import patch

        with patch.object(t, "_read_loop", new_callable=AsyncMock):
            await t.start()
        assert t._running is True
        assert t._task is not None
        t._task.cancel()

    async def test_stop(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn)
        t._running = True
        t._task = asyncio.create_task(asyncio.sleep(100))
        await t.stop()
        assert t._running is False
        assert t._task.cancelled()

    async def test_stop_no_task(self):
        t = CLITransport(conversation_manager_send=AsyncMock())
        t._running = True
        t._task = None
        await t.stop()
        assert t._running is False

    async def test_read_loop_quit(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn, tenant_id="test")
        t._running = True
        from unittest.mock import patch

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline.side_effect = ["quit\n"]
            await t._read_loop()
        assert t._running is False

    async def test_read_loop_message(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn, tenant_id="test")
        t._running = True
        from unittest.mock import patch

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline.side_effect = ["hello\n", ""]
            await t._read_loop()
        send_fn.assert_called_once()
        payload = send_fn.call_args[0][0]
        assert payload["text"] == "hello"

    async def test_read_loop_empty_line_skipped(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn, tenant_id="test")
        t._running = True
        from unittest.mock import patch

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline.side_effect = ["\n", "actual\n", ""]
            await t._read_loop()
        assert send_fn.call_count == 1

    async def test_read_loop_eof(self):
        send_fn = AsyncMock()
        t = CLITransport(conversation_manager_send=send_fn, tenant_id="test")
        t._running = True
        from unittest.mock import patch

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.readline.side_effect = [""]
            await t._read_loop()
        send_fn.assert_not_called()
