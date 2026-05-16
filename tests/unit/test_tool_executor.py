from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from nexus.agents.tool_executor import ToolExecutor, _extract_action_urls
from nexus.governance.audit import AuditSink
from nexus.governance.policy import PolicyDecision, PolicyEngine
from nexus.governance.trust import TrustStore
from nexus.llm.client import LLMResponse
from nexus.models.tenant import TenantContext


def _make_executor(**overrides) -> ToolExecutor:
    return ToolExecutor(
        llm=overrides.get("llm", AsyncMock()),
        mcp=overrides.get("mcp"),
        policy=overrides.get("policy", PolicyEngine()),
        trust=overrides.get("trust", TrustStore()),
        audit=overrides.get("audit", AuditSink("/dev/null")),
    )


def _make_tool_call(name: str = "search_gmail", tc_id: str = "tc1", input: dict | None = None):
    tc = MagicMock()
    tc.name = name
    tc.id = tc_id
    tc.input = input or {"query": "test"}
    return tc


def _make_tenant(tenant_id: str = "t1") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, name="Alice")


class TestExtractActionUrls:
    def test_oauth_keyword_extracted(self) -> None:
        url = "https://accounts.google.com/oauth/authorize?client_id=123"
        result = _extract_action_urls(f"Click: {url}")
        assert result == [url]

    def test_authorize_keyword_extracted(self) -> None:
        url = "https://example.com/authorize/callback?token=abcdef"
        result = _extract_action_urls(f"Visit: {url}")
        assert result == [url]

    def test_auth_keyword_extracted(self) -> None:
        url = "https://api.example.com/auth/login?redirect=true"
        result = _extract_action_urls(url)
        assert result == [url]

    def test_login_keyword_extracted(self) -> None:
        url = "https://service.example.com/login/sso?provider=google"
        result = _extract_action_urls(url)
        assert result == [url]

    def test_callback_keyword_extracted(self) -> None:
        url = "https://myapp.example.com/callback?code=xyz123abc"
        result = _extract_action_urls(url)
        assert result == [url]

    def test_consent_keyword_extracted(self) -> None:
        url = "https://accounts.google.com/consent?scopes=email,calendar"
        result = _extract_action_urls(url)
        assert result == [url]

    def test_regular_url_not_extracted(self) -> None:
        result = _extract_action_urls("See docs: https://example.com/documentation/api-reference")
        assert result == []

    def test_short_url_not_extracted(self) -> None:
        result = _extract_action_urls("Go to https://t.co/abc")
        assert result == []

    def test_multiple_urls_only_auth_ones_returned(self) -> None:
        oauth_url = "https://auth.example.com/oauth/token?grant_type=code"
        regular_url = "https://docs.example.com/reference/overview-guide"
        result = _extract_action_urls(f"{oauth_url} and {regular_url}")
        assert result == [oauth_url]

    def test_empty_string(self) -> None:
        assert _extract_action_urls("") == []

    def test_no_urls_in_text(self) -> None:
        assert _extract_action_urls("just some plain text with no URLs here") == []


class TestToolExecutorExecute:
    async def test_no_tool_calls_returns_directly(self) -> None:
        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="hello")
        executor = _make_executor(llm=llm)
        result = await executor.execute(
            [{"role": "user", "content": "hi"}], "", None, _make_tenant()
        )
        assert result.content == "hello"
        llm.chat.assert_called_once()

    async def test_tool_call_with_content(self) -> None:
        llm = AsyncMock()
        tc = _make_tool_call()
        first_resp = LLMResponse(content="Let me look that up for you.", tool_calls=[tc])
        second_resp = LLMResponse(content="Found 3 emails.")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = "email data"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        messages: list = [{"role": "user", "content": "check email"}]
        result = await executor.execute(messages, "", [{}], _make_tenant())

        assert result.content == "Found 3 emails."
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Let me look that up for you."

    async def test_tool_call_without_content_no_key_in_assistant_msg(self) -> None:
        llm = AsyncMock()
        tc = _make_tool_call()
        first_resp = LLMResponse(content="", tool_calls=[tc])
        second_resp = LLMResponse(content="Done.")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = "result"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        messages: list = [{"role": "user", "content": "do it"}]
        await executor.execute(messages, "", [{}], _make_tenant())

        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        assert "content" not in assistant_msgs[0]

    async def test_fallback_on_no_content(self) -> None:
        llm = AsyncMock()
        tc = _make_tool_call()
        llm.chat.return_value = LLMResponse(content="", tool_calls=[tc])

        mcp = AsyncMock()
        mcp.call_tool.return_value = "Inbox has 5 unread messages."
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        result = await executor.execute(
            [{"role": "user", "content": "check email"}], "", [{}], _make_tenant()
        )

        assert "Here's what I found:" in result.content
        assert "Inbox has 5 unread messages." in result.content

    async def test_max_iterations(self) -> None:
        from nexus.agents import tool_executor as te_module

        llm = AsyncMock()
        tc = _make_tool_call()
        llm.chat.return_value = LLMResponse(content="", tool_calls=[tc])

        mcp = AsyncMock()
        mcp.call_tool.return_value = "partial data"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        await executor.execute([{"role": "user", "content": "loop"}], "", [{}], _make_tenant())

        assert llm.chat.call_count == te_module._MAX_TOOL_ITERATIONS

    async def test_response_none_when_zero_iterations(self) -> None:
        from nexus.agents import tool_executor as te_module

        original = te_module._MAX_TOOL_ITERATIONS
        te_module._MAX_TOOL_ITERATIONS = 0
        try:
            executor = _make_executor()
            result = await executor.execute(
                [{"role": "user", "content": "hi"}], "", None, _make_tenant()
            )
            assert result.content == "I couldn't complete that request."
        finally:
            te_module._MAX_TOOL_ITERATIONS = original

    async def test_action_url_capture(self) -> None:
        llm = AsyncMock()
        tc = _make_tool_call(name="connect_google")
        oauth_url = "https://accounts.google.com/oauth/authorize?client_id=nexus&scope=email"
        first_resp = LLMResponse(content="", tool_calls=[tc])
        second_resp = LLMResponse(content="Please connect your Google account.")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = f"To connect your account visit: {oauth_url}"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        result = await executor.execute(
            [{"role": "user", "content": "connect google"}], "", [{}], _make_tenant()
        )

        assert "Please connect your Google account." in result.content
        assert oauth_url in result.content
        assert "🔗" in result.content

    async def test_action_url_already_in_response(self) -> None:
        llm = AsyncMock()
        tc = _make_tool_call(name="connect_google")
        oauth_url = "https://accounts.google.com/oauth/authorize?client_id=nexus&scope=email"
        first_resp = LLMResponse(content="", tool_calls=[tc])
        second_resp = LLMResponse(content=f"Click here to authorize: {oauth_url}")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = f"Auth URL: {oauth_url}"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        result = await executor.execute(
            [{"role": "user", "content": "connect google"}], "", [{}], _make_tenant()
        )

        assert result.content.count(oauth_url) == 1
        assert "🔗" not in result.content

    async def test_multiple_tool_calls_in_one_response(self) -> None:
        llm = AsyncMock()
        tc1 = _make_tool_call(name="search_gmail", tc_id="tc1")
        tc2 = _make_tool_call(name="search_calendar", tc_id="tc2")
        first_resp = LLMResponse(content="", tool_calls=[tc1, tc2])
        second_resp = LLMResponse(content="Checked email and calendar.")
        llm.chat.side_effect = [first_resp, second_resp]

        mcp = AsyncMock()
        mcp.call_tool.return_value = "results"
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9

        executor = _make_executor(llm=llm, mcp=mcp, policy=policy, trust=trust)
        result = await executor.execute(
            [{"role": "user", "content": "check both"}], "", [{}], _make_tenant()
        )

        assert mcp.call_tool.call_count == 2
        assert result.content == "Checked email and calendar."


class TestRunWithGovernance:
    async def test_deny_returns_not_allowed(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.DENY
        trust = MagicMock()
        trust.get_score.return_value = 0.3
        executor = _make_executor(policy=policy, trust=trust)
        result = await executor._run_with_governance("delete_email", {}, _make_tenant())
        assert "not allowed" in result

    async def test_deny_decrements_trust(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.DENY
        trust = MagicMock()
        trust.get_score.return_value = 0.3
        executor = _make_executor(policy=policy, trust=trust)
        await executor._run_with_governance("delete_email", {}, _make_tenant())
        args = trust.update_score.call_args[0]
        assert args[0] == "t1"
        assert args[2] == -0.15

    async def test_allow_calls_mcp(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9
        mcp = AsyncMock()
        mcp.call_tool.return_value = "done"
        executor = _make_executor(policy=policy, trust=trust, mcp=mcp)
        result = await executor._run_with_governance("search_gmail", {}, _make_tenant())
        assert result == "done"
        trust.update_score.assert_not_called()

    async def test_require_approval_logs_info_and_proceeds(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.REQUIRE_APPROVAL
        trust = MagicMock()
        trust.get_score.return_value = 0.6
        mcp = AsyncMock()
        mcp.call_tool.return_value = "approved result"
        executor = _make_executor(policy=policy, trust=trust, mcp=mcp)

        with patch("nexus.agents.tool_executor.logger") as mock_logger:
            result = await executor._run_with_governance("send_email", {}, _make_tenant())

        mock_logger.info.assert_called_once_with("Tool '%s' requires approval", "send_email")
        assert result == "approved result"
        trust.update_score.assert_not_called()

    async def test_require_approval_no_mcp_returns_not_available(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.REQUIRE_APPROVAL
        trust = MagicMock()
        trust.get_score.return_value = 0.6
        executor = _make_executor(policy=policy, trust=trust, mcp=None)

        with patch("nexus.agents.tool_executor.logger"):
            result = await executor._run_with_governance("send_email", {}, _make_tenant())

        assert "not available" in result

    async def test_no_mcp_returns_not_available(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.ALLOW
        trust = MagicMock()
        trust.get_score.return_value = 0.9
        executor = _make_executor(policy=policy, trust=trust, mcp=None)
        result = await executor._run_with_governance("search_gmail", {}, _make_tenant())
        assert "not available" in result

    async def test_audit_always_logged(self) -> None:
        policy = MagicMock()
        policy.check.return_value = PolicyDecision.DENY
        trust = MagicMock()
        trust.get_score.return_value = 0.3
        audit = MagicMock()
        executor = _make_executor(policy=policy, trust=trust, audit=audit)
        await executor._run_with_governance("delete_email", {"id": "123"}, _make_tenant())
        audit.log.assert_called_once()
