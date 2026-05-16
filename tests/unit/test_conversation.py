from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from civitas.messages import Message

from nexus.agents.conversation import ConversationManager
from nexus.agents.help import build_capabilities_section
from nexus.agents.intent import Intent
from nexus.governance.policy import PolicyDecision
from nexus.llm.client import LLMResponse
from nexus.models.session import Session
from nexus.models.tenant import TenantContext
from nexus.skills.parser import Skill, SkillSection


def _make_conv(**overrides) -> ConversationManager:
    defaults = {
        "name": "conversation_manager",
        "llm_base_url": "http://test:4000",
        "llm_api_key": "k",
        "llm_model": "test-model",
        "llm_cheap_model": "cheap",
        "llm_max_tokens": 100,
        "personas_dir": "/tmp/p",
        "users_dir": "/tmp/u",
        "skills_dir": "/tmp/s",
        "audit_path": "/tmp/audit.jsonl",
    }
    defaults.update(overrides)
    return ConversationManager(**defaults)


def _msg(action: str, **extra) -> Message:
    payload = {"action": action, **extra}
    m = Message(sender="test", recipient="conversation_manager", payload=payload, reply_to="test")
    return m


class TestInit:
    def test_fields_set(self) -> None:
        c = _make_conv()
        assert c._llm_model == "test-model"
        assert c._sessions == {}
        assert c._pending_approvals == {}


class TestOnStartStop:
    async def test_on_start(self) -> None:
        c = _make_conv()
        await c.on_start()
        assert c._llm is not None
        assert c._mcp is not None
        assert c._persona_loader is not None

    async def test_on_stop(self) -> None:
        c = _make_conv()
        await c.on_start()
        await c.on_stop()
        assert c._llm is None
        assert c._mcp is None


class TestSetters:
    def test_set_transport(self) -> None:
        c = _make_conv()
        t = MagicMock()
        c.set_transport(t)
        assert c._formatter._default_transport is t

    def test_set_mcp_manager(self) -> None:
        c = _make_conv()
        m = MagicMock()
        c.set_mcp_manager(m)
        assert c._mcp is m

    def test_set_content_store(self) -> None:
        c = _make_conv()
        s = MagicMock()
        d = MagicMock()
        c.set_content_store(s, d)
        assert c._formatter._content_store is s
        assert c._formatter._dashboard_config is d

    def test_set_media_handler(self) -> None:
        c = _make_conv()
        h = MagicMock()
        c.set_media_handler(h)
        assert c._media_handler is h


class TestHandle:
    async def test_dispatch_status(self) -> None:
        c = _make_conv()
        c._current_message = _msg("status")
        result = await c.handle(_msg("status"))
        assert result is not None
        assert result.payload["status"] == "running"

    async def test_unknown_action(self) -> None:
        c = _make_conv()
        result = await c.handle(_msg("unknown_xyz"))
        assert result is None

    async def test_mcp_health(self) -> None:
        c = _make_conv()
        c._mcp = None
        result = await c.handle(_msg("mcp_health_check"))
        assert result is None


class TestHandleStatus:
    async def test_returns_session_count(self) -> None:
        c = _make_conv()
        c._sessions["t1"] = Session(session_id="s1", tenant_id="t1")
        c._current_message = _msg("status")
        result = await c.handle(_msg("status"))
        assert result.payload["active_sessions"] == 1


class TestResolveTenant:
    async def test_memory_success(self) -> None:
        c = _make_conv()
        mem_resp = Message(
            sender="memory",
            recipient="test",
            payload={"tenant_id": "t1", "name": "Alice", "role": "admin", "timezone": "UTC"},
        )
        persona_resp = Message(
            sender="memory",
            recipient="test",
            payload={"persona_name": "dross"},
        )
        c.ask = AsyncMock(side_effect=[mem_resp, persona_resp])
        tenant = await c._resolve_tenant("t1")
        assert tenant is not None
        assert tenant.tenant_id == "t1"
        assert tenant.name == "Alice"

    async def test_memory_failure_fallback(self) -> None:
        c = _make_conv()
        c.ask = AsyncMock(side_effect=Exception("timeout"))
        tenant = await c._resolve_tenant("t1")
        assert tenant.tenant_id == "t1"
        assert tenant.role == "admin"


class TestGetOrCreateSession:
    async def test_existing_session(self) -> None:
        c = _make_conv()
        tenant = TenantContext(tenant_id="t1", name="A")
        s = Session(session_id="s1", tenant_id="t1")
        c._sessions["t1"] = s
        result = await c._get_or_create_session(tenant)
        assert result is s

    async def test_restore_from_memory(self) -> None:
        c = _make_conv()
        tenant = TenantContext(tenant_id="t1", name="A")
        mem_resp = Message(
            sender="memory",
            recipient="test",
            payload={"session_id": "s1", "checkpoint": None},
        )
        c.ask = AsyncMock(return_value=mem_resp)
        result = await c._get_or_create_session(tenant)
        assert result.session_id == "s1"

    async def test_create_new_on_failure(self) -> None:
        c = _make_conv()
        tenant = TenantContext(tenant_id="t1", name="A")
        c.ask = AsyncMock(side_effect=Exception("fail"))
        result = await c._get_or_create_session(tenant)
        assert result.tenant_id == "t1"
        assert result.session_id


class TestBuildCapabilities:
    def test_with_mcp_tools(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = [{"name": "t1"}, {"name": "t2"}]
        result = build_capabilities_section({}, mcp, None)
        assert "2 tools" in result

    def test_with_mcp_no_tools(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = []
        result = build_capabilities_section({}, mcp, None)
        assert "No MCP tools" in result

    def test_no_mcp(self) -> None:
        result = build_capabilities_section({}, None, None)
        assert "No MCP connection" in result

    def test_with_media_handler_vision(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = []
        media = MagicMock()
        media.has_vision = True
        result = build_capabilities_section({}, mcp, media)
        assert "analyze images" in result

    def test_no_media_handler(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = []
        result = build_capabilities_section({}, mcp, None)
        assert "not available" in result


class TestBuildMessages:
    def test_includes_history_and_current(self) -> None:
        c = _make_conv()
        session = Session(session_id="s1", tenant_id="t1")
        session.add_message("user", "prev")
        msgs = c._build_messages(session, "current")
        assert len(msgs) == 2
        assert msgs[0]["content"] == "prev"
        assert msgs[1]["content"] == "current"


class TestGetToolsForIntent:
    def test_no_mcp(self) -> None:
        c = _make_conv()
        c._mcp = None
        result = c._get_tools_for_intent(Intent(original_text="hi"))
        assert result is None

    def test_with_tool_groups(self) -> None:
        c = _make_conv()
        c._mcp = MagicMock()
        c._mcp.filter_tools.return_value = [{"type": "function"}]
        intent = Intent(tool_groups=["gmail"], original_text="check mail")
        result = c._get_tools_for_intent(intent)
        assert len(result) == 1

    def test_fallback_to_all(self) -> None:
        c = _make_conv()
        c._mcp = MagicMock()
        c._mcp.filter_tools.return_value = []
        c._mcp.all_tool_schemas.return_value = [{"type": "function"}]
        intent = Intent(tool_groups=["gmail"], original_text="check mail")
        result = c._get_tools_for_intent(intent)
        assert len(result) == 1


class TestToolExecutor:
    def _make_executor(self, **overrides):
        from nexus.agents.tool_executor import ToolExecutor
        from nexus.governance.audit import AuditSink
        from nexus.governance.policy import PolicyEngine
        from nexus.governance.trust import TrustStore

        return ToolExecutor(
            llm=overrides.get("llm", AsyncMock()),
            mcp=overrides.get("mcp"),
            policy=overrides.get("policy", PolicyEngine()),
            trust=overrides.get("trust", TrustStore()),
            audit=overrides.get("audit", AuditSink("/dev/null")),
        )

    async def test_no_tool_calls(self) -> None:
        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="hello")
        executor = self._make_executor(llm=llm)
        tenant = TenantContext(tenant_id="t1", name="A")
        result = await executor.execute([{"role": "user", "content": "hi"}], "", None, tenant)
        assert result.content == "hello"

    async def test_with_tool_calls(self) -> None:
        llm = AsyncMock()
        tc = MagicMock()
        tc.name = "search_gmail"
        tc.id = "tc1"
        tc.input = {"query": "test"}
        first_resp = LLMResponse(content="", tool_calls=[tc])
        second_resp = LLMResponse(content="Found 2 emails")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = "result data"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.8

        executor = self._make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        tenant = TenantContext(tenant_id="t1", name="A")
        result = await executor.execute(
            [{"role": "user", "content": "check email"}], "", [{}], tenant
        )
        assert result.content == "Found 2 emails"

    async def test_deny(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.DENY
        trust = MagicMock()
        trust.get_score.return_value = 0.3
        executor = self._make_executor(policy=policy, trust=trust)
        tenant = TenantContext(tenant_id="t1", name="A")
        result = await executor._run_with_governance("delete_email", {}, tenant)
        assert "not allowed" in result
        trust.update_score.assert_called_once()

    async def test_allow(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9
        mcp = AsyncMock()
        mcp.call_tool.return_value = "done"
        executor = self._make_executor(policy=policy, trust=trust, mcp=mcp)
        tenant = TenantContext(tenant_id="t1", name="A")
        result = await executor._run_with_governance("search_gmail", {}, tenant)
        assert result == "done"

    async def test_no_mcp(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9
        executor = self._make_executor(policy=policy, trust=trust, mcp=None)
        tenant = TenantContext(tenant_id="t1", name="A")
        result = await executor._run_with_governance("search_gmail", {}, tenant)
        assert "not available" in result


class TestHandleInbound:
    async def test_no_tenant_id(self) -> None:
        c = _make_conv()
        result = await c._handle_inbound(_msg("inbound_message"))
        assert result is None

    async def test_unauthorized(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.ask = AsyncMock(side_effect=Exception("no"))
        msg = _msg("inbound_message", tenant_id="bad", text="hi", channel_id="c1")
        await c._handle_inbound(msg)
        c._formatter._default_transport.send_text.assert_called_once()

    async def test_happy_path(self) -> None:
        from nexus.agents.tool_executor import ToolExecutor

        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.ask = AsyncMock(side_effect=Exception("skip"))
        c.send = AsyncMock()
        c.cast = AsyncMock()
        c._llm = AsyncMock()
        c._llm.chat.return_value = LLMResponse(content="Hi there!")
        c._tool_executor = ToolExecutor(
            llm=c._llm,
            mcp=None,
            policy=c._policy,
            trust=c._trust,
            audit=c._audit,
        )
        c._persona_loader = MagicMock()
        c._persona_loader.build_system_identity.return_value = "You are test."
        c._classifier = MagicMock()
        c._classifier.classify = AsyncMock(return_value=Intent(original_text="hi"))

        msg = _msg("inbound_message", tenant_id="t1", text="hi", channel_id="c1")
        await c._handle_inbound(msg)

        c._formatter._default_transport.send_text.assert_called()

    async def test_llm_failure(self) -> None:
        from nexus.agents.tool_executor import ToolExecutor

        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.ask = AsyncMock(side_effect=Exception("skip"))
        c.send = AsyncMock()
        c.cast = AsyncMock()
        c._llm = AsyncMock()
        c._llm.chat.side_effect = Exception("LLM down")
        c._tool_executor = ToolExecutor(
            llm=c._llm,
            mcp=None,
            policy=c._policy,
            trust=c._trust,
            audit=c._audit,
        )
        c._persona_loader = MagicMock()
        c._persona_loader.build_system_identity.return_value = "You are test."
        c._classifier = MagicMock()
        c._classifier.classify = AsyncMock(return_value=Intent(original_text="hi"))

        msg = _msg("inbound_message", tenant_id="t1", text="hi", channel_id="c1")
        await c._handle_inbound(msg)

        sent_text = c._formatter._default_transport.send_text.call_args[0][1]
        assert "trouble" in sent_text


class TestHandleSkillTrigger:
    async def test_missing_skill_name(self) -> None:
        c = _make_conv()
        result = await c._handle_skill_trigger(_msg("execute_skill", tenant_id="t1"))
        assert result is None

    async def test_skill_not_found(self) -> None:
        c = _make_conv()
        c._skill_manager = MagicMock()
        c._skill_manager.get.return_value = None
        c.ask = AsyncMock(side_effect=Exception("skip"))
        result = await c._handle_skill_trigger(
            _msg("execute_skill", skill_name="missing", tenant_id="t1")
        )
        assert result is None


class TestHandleTransportCallback:
    async def test_approve(self) -> None:
        c = _make_conv()
        c._pending_approvals["abc"] = {"tool_name": "search_gmail"}
        c._formatter.set_default_transport(AsyncMock())
        msg = _msg("callback", callback_data="approve:abc", tenant_id="t1", channel_id="c1")
        await c._handle_transport_callback(msg)
        assert "abc" not in c._pending_approvals

    async def test_reject(self) -> None:
        c = _make_conv()
        c._pending_approvals["abc"] = {"tool_name": "search_gmail"}
        c._formatter.set_default_transport(AsyncMock())
        msg = _msg("callback", callback_data="reject:abc", tenant_id="t1", channel_id="c1")
        await c._handle_transport_callback(msg)
        assert "abc" not in c._pending_approvals

    async def test_unknown_callback(self) -> None:
        c = _make_conv()
        msg = _msg("callback", callback_data="xyz:nope", tenant_id="t1", channel_id="c1")
        result = await c._handle_transport_callback(msg)
        assert result is None


class TestHandleCommand:
    async def test_unknown_command(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        msg = _msg("command", command="bogus", args="", tenant_id="t1", channel_id="c1")
        await c._handle_command(msg)
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "Unknown command" in sent

    async def test_status_command(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.ask = AsyncMock(side_effect=Exception("no dashboard"))
        msg = _msg("command", command="status", args="", tenant_id="t1", channel_id="c1")
        await c._handle_command(msg)
        c._formatter._default_transport.send_text.assert_called()


class TestCheckpoint:
    async def test_no_session(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        await c._handle_checkpoint("t1", "c1", "")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "No active session" in sent

    async def test_success(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.send = AsyncMock()
        c._sessions["t1"] = Session(session_id="s1", tenant_id="t1")
        await c._handle_checkpoint("t1", "c1", "my-cp")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "my-cp" in sent

    async def test_failure(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.send = AsyncMock(side_effect=Exception("fail"))
        c._sessions["t1"] = Session(session_id="s1", tenant_id="t1")
        await c._handle_checkpoint("t1", "c1", "cp")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "Failed" in sent


class TestRollback:
    async def test_no_label_lists(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        resp = Message(
            sender="memory",
            recipient="test",
            payload={"configs": {"checkpoints": {"cp1": "data"}}},
        )
        c.ask = AsyncMock(return_value=resp)
        await c._handle_rollback("t1", "c1", "")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "cp1" in sent

    async def test_no_label_no_checkpoints(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        resp = Message(sender="memory", recipient="test", payload={"configs": {}})
        c.ask = AsyncMock(return_value=resp)
        await c._handle_rollback("t1", "c1", "")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "No checkpoints" in sent

    async def test_restore_success(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c.send = AsyncMock()
        session_data = Session(session_id="s1", tenant_id="t1").to_dict()
        resp = Message(
            sender="memory",
            recipient="test",
            payload={"value": json.dumps(session_data)},
        )
        c.ask = AsyncMock(return_value=resp)
        await c._handle_rollback("t1", "c1", "cp1")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "Rolled back" in sent

    async def test_not_found(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        resp = Message(sender="memory", recipient="test", payload={"value": None})
        c.ask = AsyncMock(return_value=resp)
        await c._handle_rollback("t1", "c1", "nope")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "not found" in sent


class TestBuildStatusReport:
    async def test_with_mcp(self) -> None:
        c = _make_conv()
        c.ask = AsyncMock(side_effect=Exception("no dash"))
        c._mcp = MagicMock()
        c._mcp.health_check = AsyncMock(return_value={"google": True})
        c._mcp.all_tool_schemas.return_value = [{}]
        c._mcp.filter_tools.return_value = []
        report = await c._build_status_report("t1")
        assert "google: connected" in report

    async def test_without_mcp(self) -> None:
        c = _make_conv()
        c.ask = AsyncMock(side_effect=Exception("no"))
        c._mcp = None
        report = await c._build_status_report("t1")
        assert "Nexus Status" in report


class TestSendReply:
    async def test_with_transport(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        await c._formatter.send_reply("c1", "hello")
        c._formatter._default_transport.send_text.assert_called_once_with("c1", "hello")

    async def test_no_transport(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(None)
        await c._formatter.send_reply("c1", "hello")
        assert c._formatter._default_transport is None

    async def test_transport_error(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        c._formatter._default_transport.send_text.side_effect = Exception("err")
        await c._formatter.send_reply("c1", "hello")
        c._formatter._default_transport.send_text.assert_called_once()
        assert c._formatter._default_transport is not None


class TestSendResponseWithViewer:
    async def test_short_response(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        await c._formatter.send_response("c1", "short text")
        c._formatter._default_transport.send_text.assert_called_once_with("c1", "short text")

    async def test_long_response_with_store(self) -> None:
        c = _make_conv()
        transport = AsyncMock()
        c._formatter.set_default_transport(transport)
        store = MagicMock()
        store.store.return_value = "abc123"
        config = MagicMock()
        config.host = "localhost"
        config.port = 8080
        config.base_url = ""
        c._formatter.set_content_store(store, config)
        long_text = "x" * 3000
        await c._formatter.send_response("c1", long_text)
        sent = transport.send_text.call_args[0][1]
        assert "abc123" in sent


class TestSendTyping:
    async def test_with_transport(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(AsyncMock())
        await c._formatter.send_typing("c1")
        c._formatter._default_transport.send_typing.assert_called_once()

    async def test_no_transport(self) -> None:
        c = _make_conv()
        c._formatter.set_default_transport(None)
        await c._formatter.send_typing("c1")
        assert c._formatter._default_transport is None


class TestProcessMedia:
    async def test_voice(self) -> None:
        c = _make_conv()
        c._media_handler = AsyncMock()
        c._media_handler.process_voice.return_value = "hello world"
        result = await c._process_media({"media_type": "voice", "_media_bytes": b"audio"}, "")
        assert result == "hello world"

    async def test_photo(self) -> None:
        c = _make_conv()
        c._media_handler = AsyncMock()
        c._media_handler.process_image.return_value = "a cat"
        result = await c._process_media(
            {"media_type": "photo", "_media_bytes": b"img", "media_caption": "what?"}, ""
        )
        assert "a cat" in result

    async def test_document(self) -> None:
        c = _make_conv()
        c._media_handler = AsyncMock()
        c._media_handler.process_document.return_value = "file content"
        result = await c._process_media(
            {"media_type": "document", "_media_bytes": b"doc", "metadata": {"filename": "f.txt"}},
            "",
        )
        assert "file content" in result

    async def test_video(self) -> None:
        c = _make_conv()
        c._media_handler = AsyncMock()
        c._media_handler.process_video.return_value = ("audio transcript", [b"frame"])
        c._media_handler.has_vision = True
        c._media_handler.process_image.return_value = "frame description"
        result = await c._process_media({"media_type": "video", "_media_bytes": b"vid"}, "")
        assert "audio transcript" in result

    async def test_video_no_results(self) -> None:
        c = _make_conv()
        c._media_handler = AsyncMock()
        c._media_handler.process_video.return_value = ("", [])
        c._media_handler.has_vision = False
        result = await c._process_media({"media_type": "video", "_media_bytes": b"vid"}, "")
        assert "Video received" in result

    async def test_no_handler(self) -> None:
        c = _make_conv()
        c._media_handler = None
        result = await c._process_media({"media_type": "voice"}, "fallback")
        assert result == "fallback"

    async def test_unknown_media_type(self) -> None:
        c = _make_conv()
        c._media_handler = MagicMock()
        result = await c._process_media({"media_type": "sticker", "_media_bytes": b""}, "original")
        assert result == "original"


class TestExecuteSkillParallel:
    async def test_parallel_sections(self) -> None:
        c = _make_conv()
        c._llm = AsyncMock()
        c._llm.chat.return_value = LLMResponse(content="Section result")
        c._llm.model_for_task.return_value = "cheap"
        c._formatter.set_default_transport(AsyncMock())

        sections = [
            SkillSection(name="Email", content="Check email"),
            SkillSection(name="Calendar", content="Check calendar"),
        ]
        skill = Skill(
            name="briefing",
            description="d",
            content="",
            execution="parallel",
            sections=sections,
        )
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_parallel(skill, tenant, "c1", None, "cheap")
        assert c._formatter._default_transport.send_text.call_count == 2

    async def test_parallel_timeout(self) -> None:
        c = _make_conv()

        async def slow_chat(**kwargs):
            await asyncio.sleep(100)
            return LLMResponse(content="late")

        c._llm = AsyncMock()
        c._llm.chat.side_effect = slow_chat
        c._formatter.set_default_transport(AsyncMock())

        sections = [SkillSection(name="Slow", content="x", timeout=0)]
        skill = Skill(
            name="test", description="d", content="", execution="parallel", sections=sections
        )
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_parallel(skill, tenant, "c1", None, "cheap")
        sent = c._formatter._default_transport.send_text.call_args[0][1]
        assert "timed out" in sent or "Slow" in sent

    async def test_parallel_not_initialized(self) -> None:
        c = _make_conv()
        c._llm = None
        c._formatter.set_default_transport(AsyncMock())
        skill = Skill(name="test", description="d", content="x", execution="parallel")
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_parallel(skill, tenant, "c1", None, "cheap")
        assert c._llm is None
        c._formatter._default_transport.send_text.assert_not_called()


class TestBuildSystemPrompt:
    async def test_with_memories_and_skills(self) -> None:
        c = _make_conv()
        c._persona_loader = MagicMock()
        c._persona_loader.build_system_identity.return_value = "You are Nexus."
        c._mcp = MagicMock()
        c._mcp.all_tool_schemas.return_value = []
        c._skill_manager = MagicMock()
        c._skill_manager.build_summary.return_value = "morning-briefing, heartbeat"

        tenant = TenantContext(tenant_id="t1", name="A")
        intent = Intent(original_text="hi")

        mem_resp = MagicMock()
        mem_resp.payload = {"results": [{"key": "fav_color", "value": "blue"}]}
        c.ask = AsyncMock(return_value=mem_resp)

        prompt = await c._build_system_prompt(tenant, intent)
        assert "You are Nexus" in prompt
        assert "fav_color" in prompt
        assert "morning-briefing" in prompt

    async def test_no_persona_loader(self) -> None:
        c = _make_conv()
        c._persona_loader = None
        tenant = TenantContext(tenant_id="t1", name="A")
        prompt = await c._build_system_prompt(tenant, Intent(original_text="hi"))
        assert prompt == ""


class TestPersistAndCheckpoint:
    async def test_persist_message_success(self) -> None:
        c = _make_conv()
        c.send = AsyncMock()
        await c._persist_message("s1", "user", "hi")
        c.send.assert_called_once()

    async def test_persist_message_failure(self) -> None:
        c = _make_conv()
        c.send = AsyncMock(side_effect=Exception("fail"))
        await c._persist_message("s1", "user", "hi")
        c.send.assert_called_once()

    async def test_checkpoint_session_success(self) -> None:
        c = _make_conv()
        c.send = AsyncMock()
        session = Session(session_id="s1", tenant_id="t1")
        await c._checkpoint_session(session)
        c.send.assert_called_once()

    async def test_checkpoint_session_failure(self) -> None:
        c = _make_conv()
        c.send = AsyncMock(side_effect=Exception("fail"))
        session = Session(session_id="s1", tenant_id="t1")
        await c._checkpoint_session(session)
        c.send.assert_called_once()


class TestLlmRespond:
    async def test_not_initialized(self) -> None:
        c = _make_conv()
        c._llm = None
        tenant = TenantContext(tenant_id="t1", name="A")
        session = Session(session_id="s1", tenant_id="t1")
        result = await c._llm_respond(session, tenant, "hi", Intent(original_text="hi"))
        assert "not fully initialized" in result

    async def test_with_compression(self) -> None:
        from nexus.agents.tool_executor import ToolExecutor

        c = _make_conv()
        c._llm = AsyncMock()
        c._llm.chat.return_value = LLMResponse(content="compressed response")
        c._tool_executor = ToolExecutor(
            llm=c._llm,
            mcp=None,
            policy=c._policy,
            trust=c._trust,
            audit=c._audit,
        )
        c._persona_loader = MagicMock()
        c._persona_loader.build_system_identity.return_value = "prompt"
        c.ask = AsyncMock(side_effect=Exception("skip"))
        c._compressor = MagicMock()
        c._compressor.needs_compression.return_value = True
        c._compressor.compress = AsyncMock(return_value=[{"role": "user", "content": "hi"}])

        tenant = TenantContext(tenant_id="t1", name="A")
        session = Session(session_id="s1", tenant_id="t1")
        result = await c._llm_respond(session, tenant, "hi", Intent(original_text="hi"))
        assert result == "compressed response"
        c._compressor.compress.assert_called_once()


class TestReportActivity:
    async def test_success(self) -> None:
        c = _make_conv()
        c.cast = AsyncMock()
        await c._report_activity("t1", "hello test message")
        c.cast.assert_called_once()

    async def test_failure_suppressed(self) -> None:
        c = _make_conv()
        c.cast = AsyncMock(side_effect=Exception("fail"))
        await c._report_activity("t1", "hi")
        c.cast.assert_called_once()


class TestReportMcpHealth:
    async def test_with_mcp(self) -> None:
        c = _make_conv()
        c._mcp = MagicMock()
        c._mcp.health_check = AsyncMock(return_value={"google": True})
        c._mcp.filter_tools.return_value = [{}]
        c.cast = AsyncMock()
        await c._report_mcp_health()
        c.cast.assert_called()

    async def test_no_mcp(self) -> None:
        c = _make_conv()
        c._mcp = None
        await c._report_mcp_health()
        assert c._mcp is None


class TestExecuteSkillSequential:
    async def test_heartbeat_ok(self) -> None:
        c = _make_conv()
        c._llm = AsyncMock()
        c._llm.chat.return_value = LLMResponse(content="HEARTBEAT_OK")
        c._llm.model_for_task.return_value = "cheap"
        c._formatter.set_default_transport(AsyncMock())
        skill = Skill(name="hb", description="d", content="check", execution="sequential")
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_sequential(skill, tenant, "c1", None, "cheap")
        c._formatter._default_transport.send_text.assert_not_called()

    async def test_normal_response(self) -> None:
        c = _make_conv()
        c._llm = AsyncMock()
        c._llm.chat.return_value = LLMResponse(content="Good morning!")
        c._formatter.set_default_transport(AsyncMock())
        skill = Skill(name="briefing", description="d", content="brief", execution="sequential")
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_sequential(skill, tenant, "c1", None, "cheap")
        c._formatter._default_transport.send_text.assert_called()

    async def test_not_initialized(self) -> None:
        c = _make_conv()
        c._llm = None
        c._formatter.set_default_transport(AsyncMock())
        skill = Skill(name="test", description="d", content="x", execution="sequential")
        tenant = TenantContext(tenant_id="t1", name="A")
        await c._execute_skill_sequential(skill, tenant, "c1", None, "cheap")
        assert c._llm is None
        c._formatter._default_transport.send_text.assert_not_called()
