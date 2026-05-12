from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from nexus.transport.discord import DiscordTransport, _split_discord


def _make_transport():
    send_fn = AsyncMock()
    resolver = MagicMock(return_value="tenant_1")
    t = DiscordTransport(
        bot_token="fake-token",
        conversation_manager_send=send_fn,
        tenant_resolver=resolver,
    )
    return t, send_fn, resolver


class TestInit:
    def test_stores_config(self) -> None:
        t, _, _ = _make_transport()
        assert t._bot_token == "fake-token"
        assert t._command_prefix == "!"

    def test_transport_name(self) -> None:
        t, _, _ = _make_transport()
        assert t.transport_name == "discord"


class TestStop:
    async def test_with_client(self) -> None:
        t, _, _ = _make_transport()
        t._client = AsyncMock()
        await t.stop()
        t._client.close.assert_called_once()

    async def test_no_client(self) -> None:
        t, _, _ = _make_transport()
        t._client = None
        await t.stop()


class TestSendText:
    async def test_no_client(self) -> None:
        t, _, _ = _make_transport()
        t._client = None
        await t.send_text("123", "hello")

    async def test_channel_not_found(self) -> None:
        t, _, _ = _make_transport()
        t._client = MagicMock()
        t._client.get_channel.return_value = None
        await t.send_text("123", "hello")

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        channel = AsyncMock()
        t._client = MagicMock()
        t._client.get_channel.return_value = channel
        await t.send_text("123", "hello")
        channel.send.assert_called_once_with("hello")

    async def test_long_message_split(self) -> None:
        t, _, _ = _make_transport()
        channel = AsyncMock()
        t._client = MagicMock()
        t._client.get_channel.return_value = channel
        await t.send_text("123", "x" * 3000)
        assert channel.send.call_count == 2


class TestSendButtons:
    async def test_no_client(self) -> None:
        t, _, _ = _make_transport()
        t._client = None
        from nexus.transport.base import Button

        await t.send_buttons("123", "Choose:", [Button(label="A", callback_data="a")])

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        channel = AsyncMock()
        t._client = MagicMock()
        t._client.get_channel.return_value = channel
        from nexus.transport.base import Button

        await t.send_buttons("123", "Pick:", [Button(label="OK", callback_data="ok")])
        channel.send.assert_called_once()


class TestSendTyping:
    async def test_no_client(self) -> None:
        t, _, _ = _make_transport()
        t._client = None
        await t.send_typing("123")

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        channel = AsyncMock()
        t._client = MagicMock()
        t._client.get_channel.return_value = channel
        await t.send_typing("123")
        channel.typing.assert_called_once()


class TestStart:
    async def test_import_error(self) -> None:
        from unittest.mock import patch

        t, _, _ = _make_transport()
        import pytest

        with patch("nexus.transport.discord._HAS_DISCORD", False):
            with pytest.raises(RuntimeError, match=r"discord\.py"):
                await t.start()


class TestSplitDiscord:
    def test_short_text(self) -> None:
        assert _split_discord("hello") == ["hello"]

    def test_exact_limit(self) -> None:
        assert _split_discord("x" * 2000) == ["x" * 2000]

    def test_long_text_with_newlines(self) -> None:
        text = ("a" * 1500 + "\n") * 3
        chunks = _split_discord(text.strip())
        assert all(len(c) <= 2000 for c in chunks)
        assert len(chunks) >= 2

    def test_long_text_no_newlines(self) -> None:
        text = "x" * 5000
        chunks = _split_discord(text)
        assert len(chunks) == 3
        assert "".join(chunks) == text
