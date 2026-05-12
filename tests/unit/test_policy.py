from __future__ import annotations

from nexus.governance.policy import PolicyDecision, PolicyEngine


class TestPolicyEngine:
    def test_read_tools_allowed(self) -> None:
        engine = PolicyEngine()
        assert engine.check("search_gmail_messages") == PolicyDecision.ALLOW
        assert engine.check("list_events") == PolicyDecision.ALLOW
        assert engine.check("get_message") == PolicyDecision.ALLOW

    def test_write_tools_require_approval(self) -> None:
        engine = PolicyEngine()
        assert engine.check("send_gmail_message") == PolicyDecision.REQUIRE_APPROVAL
        assert engine.check("create_event") == PolicyDecision.REQUIRE_APPROVAL
        assert engine.check("delete_event") == PolicyDecision.REQUIRE_APPROVAL
        assert engine.check("update_event") == PolicyDecision.REQUIRE_APPROVAL

    def test_unknown_tools_allowed(self) -> None:
        engine = PolicyEngine()
        assert engine.check("some_custom_tool") == PolicyDecision.ALLOW

    def test_deny_patterns(self) -> None:
        engine = PolicyEngine(deny_patterns=["dangerous_tool"])
        assert engine.check("dangerous_tool") == PolicyDecision.DENY

    def test_deny_takes_precedence(self) -> None:
        engine = PolicyEngine(deny_patterns=["search_secret"])
        assert engine.check("search_secret_data") == PolicyDecision.DENY

    def test_private_url_denied(self) -> None:
        engine = PolicyEngine()
        assert (
            engine.check("send_message", {"url": "http://192.168.1.1/api"}) == PolicyDecision.DENY
        )

    def test_private_url_localhost(self) -> None:
        engine = PolicyEngine()
        assert engine.check("send_message", {"url": "http://127.0.0.1:8080"}) == PolicyDecision.DENY

    def test_public_url_allowed(self) -> None:
        engine = PolicyEngine()
        result = engine.check("search_gmail_messages", {"url": "https://google.com"})
        assert result == PolicyDecision.ALLOW

    def test_high_trust_allows_write(self) -> None:
        engine = PolicyEngine()
        assert engine.check("send_gmail_message", trust_score=0.9) == PolicyDecision.ALLOW

    def test_low_trust_denies(self) -> None:
        engine = PolicyEngine()
        assert engine.check("send_gmail_message", trust_score=0.3) == PolicyDecision.DENY

    def test_no_trust_score_requires_approval(self) -> None:
        engine = PolicyEngine()
        assert (
            engine.check("send_gmail_message", trust_score=None) == PolicyDecision.REQUIRE_APPROVAL
        )

    def test_contains_private_url_non_string(self) -> None:
        assert PolicyEngine._contains_private_url({"count": 42}) is False
