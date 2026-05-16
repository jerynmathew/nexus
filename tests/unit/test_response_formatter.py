from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from nexus.agents.response_formatter import ResponseFormatter
from nexus.config import DashboardConfig
from nexus.dashboard.views import ContentStore


class TestAddTransportAndSendReply:
    async def test_add_transport_routes_by_prefix(self) -> None:
        telegram = MagicMock()
        telegram.send_text = AsyncMock()
        formatter = ResponseFormatter()
        formatter.add_transport("tg:", telegram)

        await formatter.send_reply("tg:123", "hello")

        telegram.send_text.assert_awaited_once_with("tg:123", "hello")

    async def test_send_reply_falls_back_to_default_transport(self) -> None:
        default = MagicMock()
        default.send_text = AsyncMock()
        formatter = ResponseFormatter(default_transport=default)
        formatter.add_transport("tg:", MagicMock())

        await formatter.send_reply("cli:456", "fallback")

        default.send_text.assert_awaited_once_with("cli:456", "fallback")

    async def test_send_reply_no_transport_no_error(self) -> None:
        formatter = ResponseFormatter()
        await formatter.send_reply("unknown:1", "text")

    async def test_send_reply_transport_exception_swallowed(self) -> None:
        transport = MagicMock()
        transport.send_text = AsyncMock(side_effect=RuntimeError("network down"))
        formatter = ResponseFormatter(default_transport=transport)

        await formatter.send_reply("any", "text")


class TestSendResponse:
    async def test_short_response_sent_directly(self) -> None:
        transport = MagicMock()
        transport.send_text = AsyncMock()
        formatter = ResponseFormatter(default_transport=transport)

        await formatter.send_response("ch1", "short")

        transport.send_text.assert_awaited_once_with("ch1", "short")

    async def test_long_response_with_base_url_uses_base_url(self, tmp_path: Path) -> None:
        transport = MagicMock()
        transport.send_text = AsyncMock()
        store = ContentStore(views_dir=str(tmp_path / "views"))
        config = DashboardConfig(base_url="https://nexus.example.com", host="localhost", port=8080)

        formatter = ResponseFormatter(
            default_transport=transport,
            content_store=store,
            dashboard_config=config,
        )
        long_text = "x" * 2001

        await formatter.send_response("ch1", long_text)

        transport.send_text.assert_awaited_once()
        sent = transport.send_text.call_args[0][1]
        assert "https://nexus.example.com/view/" in sent
        assert "localhost" not in sent

    async def test_long_response_without_base_url_uses_host_port(self, tmp_path: Path) -> None:
        transport = MagicMock()
        transport.send_text = AsyncMock()
        store = ContentStore(views_dir=str(tmp_path / "views"))
        config = DashboardConfig(base_url="", host="myhost", port=9090)

        formatter = ResponseFormatter(
            default_transport=transport,
            content_store=store,
            dashboard_config=config,
        )
        long_text = "y" * 2001

        await formatter.send_response("ch1", long_text)

        transport.send_text.assert_awaited_once()
        sent = transport.send_text.call_args[0][1]
        assert "http://myhost:9090/view/" in sent

    async def test_long_response_no_content_store_sent_directly(self) -> None:
        transport = MagicMock()
        transport.send_text = AsyncMock()
        formatter = ResponseFormatter(default_transport=transport)
        long_text = "z" * 2001

        await formatter.send_response("ch1", long_text)

        transport.send_text.assert_awaited_once_with("ch1", long_text)


class TestSetContentStore:
    def test_set_content_store_updates_both_fields(self, tmp_path: Path) -> None:
        formatter = ResponseFormatter()
        store = ContentStore(views_dir=str(tmp_path / "views"))
        config = DashboardConfig()

        formatter.set_content_store(store, config)

        assert formatter._content_store is store
        assert formatter._dashboard_config is config


class TestSetDefaultTransport:
    def test_set_default_transport(self) -> None:
        formatter = ResponseFormatter()
        transport = MagicMock()
        formatter.set_default_transport(transport)
        assert formatter._default_transport is transport


class TestSendTyping:
    async def test_send_typing_delegated_to_transport(self) -> None:
        transport = MagicMock()
        transport.send_typing = AsyncMock()
        formatter = ResponseFormatter(default_transport=transport)

        await formatter.send_typing("ch1")

        transport.send_typing.assert_awaited_once_with("ch1")

    async def test_send_typing_exception_suppressed(self) -> None:
        transport = MagicMock()
        transport.send_typing = AsyncMock(side_effect=RuntimeError("boom"))
        formatter = ResponseFormatter(default_transport=transport)

        await formatter.send_typing("ch1")
