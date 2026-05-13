from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import nexus.transport.discord as dtmod
from nexus.transport.base import Button
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
        await t.send_buttons("123", "Choose:", [Button(label="A", callback_data="a")])

    async def test_success(self) -> None:
        t, _, _ = _make_transport()
        channel = AsyncMock()
        t._client = MagicMock()
        t._client.get_channel.return_value = channel
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
        t, _, _ = _make_transport()
        with patch("nexus.transport.discord._HAS_DISCORD", False):
            with pytest.raises(RuntimeError, match=r"discord\.py"):
                await t.start()


def _inject_discord_mock():
    mock_discord_mod = MagicMock(spec=ModuleType)
    mock_discord_mod.Intents.default.return_value = MagicMock()
    return patch.dict(sys.modules, {"discord": mock_discord_mod}), mock_discord_mod


def _start_discord_with_handlers(t):
    mock_client = MagicMock()
    handlers = {}

    def capture_event(fn):
        handlers[fn.__name__] = fn
        return fn

    mock_client.event = capture_event
    mock_client.start = AsyncMock()
    mock_client.user = MagicMock()
    mock_client.user.id = 999

    original_has = dtmod._HAS_DISCORD
    dtmod._HAS_DISCORD = True
    old_discord = getattr(dtmod, "discord", None)
    mock_discord = MagicMock()
    mock_discord.Intents.default.return_value = MagicMock()
    mock_discord.Client.return_value = mock_client
    dtmod.discord = mock_discord  # type: ignore[attr-defined]

    return mock_client, handlers, original_has, old_discord


def _cleanup_discord(t, original_has, old_discord):
    dtmod._HAS_DISCORD = original_has
    if old_discord is not None:
        dtmod.discord = old_discord  # type: ignore[attr-defined]
    elif hasattr(dtmod, "discord"):
        del dtmod.discord  # type: ignore[attr-defined]


class TestOnMessage:
    async def test_start_registers_handlers(self) -> None:
        t, _send_fn, _resolver = _make_transport()
        mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            assert t._client is mock_client
            assert "on_ready" in handlers
            assert "on_message" in handlers
        finally:
            _cleanup_discord(t, orig, old)

    async def test_message_from_self_ignored(self) -> None:
        t, send_fn, _resolver = _make_transport()
        mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = mock_client.user
            await handlers["on_message"](msg)
            send_fn.assert_not_called()
        finally:
            _cleanup_discord(t, orig, old)

    async def test_message_from_bot_ignored(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = True
            await handlers["on_message"](msg)
            send_fn.assert_not_called()
        finally:
            _cleanup_discord(t, orig, old)

    async def test_non_dm_non_mention_ignored(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.channel.guild = MagicMock()
            msg.mentions = []
            await handlers["on_message"](msg)
            send_fn.assert_not_called()
        finally:
            _cleanup_discord(t, orig, old)

    async def test_unauthorized_user(self) -> None:
        t, _send_fn, resolver = _make_transport()
        resolver.return_value = None
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = AsyncMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.author.id = 12345
            msg.channel.guild = None
            msg.content = "hello"
            await handlers["on_message"](msg)
            msg.channel.send.assert_called_once_with("Sorry, you're not authorized.")
        finally:
            _cleanup_discord(t, orig, old)

    async def test_dm_text_message(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.author.id = 12345
            msg.channel.guild = None
            msg.content = "hello there"
            msg.id = 777
            msg.mentions = []
            await handlers["on_message"](msg)
            send_fn.assert_called_once()
            payload = send_fn.call_args[0][0]
            assert payload["action"] == "inbound_message"
        finally:
            _cleanup_discord(t, orig, old)

    async def test_command_message(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.author.id = 12345
            msg.channel.guild = None
            msg.channel.id = 42
            msg.content = "!status"
            msg.mentions = []
            await handlers["on_message"](msg)
            send_fn.assert_called_once()
            payload = send_fn.call_args[0][0]
            assert payload["action"] == "command"
            assert payload["command"] == "status"
        finally:
            _cleanup_discord(t, orig, old)

    async def test_mention_strips_user_id(self) -> None:
        t, send_fn, _resolver = _make_transport()
        mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            user = mock_client.user
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.author.id = 12345
            msg.channel.guild = MagicMock()
            msg.channel.id = 42
            msg.id = 888
            msg.content = f"<@{user.id}> hello bot"
            msg.mentions = [user]
            await handlers["on_message"](msg)
            send_fn.assert_called_once()
            payload = send_fn.call_args[0][0]
            assert payload["action"] == "inbound_message"
        finally:
            _cleanup_discord(t, orig, old)

    async def test_on_ready_handler(self) -> None:
        t, _send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            await handlers["on_ready"]()
        finally:
            _cleanup_discord(t, orig, old)

    async def test_command_with_args(self) -> None:
        t, send_fn, _resolver = _make_transport()
        _mock_client, handlers, orig, old = _start_discord_with_handlers(t)
        try:
            await t.start()
            msg = MagicMock()
            msg.author = MagicMock()
            msg.author.bot = False
            msg.author.id = 12345
            msg.channel.guild = None
            msg.channel.id = 42
            msg.content = "!research best fund"
            msg.mentions = []
            await handlers["on_message"](msg)
            payload = send_fn.call_args[0][0]
            assert payload["command"] == "research"
            assert payload["args"] == "best fund"
        finally:
            _cleanup_discord(t, orig, old)


class TestSendTypingChannelNotFound:
    async def test_channel_not_found(self) -> None:
        t, _, _ = _make_transport()
        t._client = MagicMock()
        t._client.get_channel.return_value = None
        await t.send_typing("123")

    async def test_buttons_channel_not_found(self) -> None:
        t, _, _ = _make_transport()
        t._client = MagicMock()
        t._client.get_channel.return_value = None
        await t.send_buttons("123", "Pick:", [Button(label="A", callback_data="a")])


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
