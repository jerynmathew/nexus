from __future__ import annotations

import pytest

from nexus.agents.intent import RegexClassifier
from nexus.models.tenant import TenantContext

_TENANT = TenantContext(tenant_id="t1", name="Test")


class TestRegexClassifier:
    @pytest.fixture()
    def classifier(self) -> RegexClassifier:
        return RegexClassifier()

    async def test_email_read(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("check my email", _TENANT)
        assert intent.target_service == "gmail"
        assert intent.action == "read"

    async def test_email_write(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("send an email to Sarah", _TENANT)
        assert intent.target_service == "gmail"
        assert intent.action == "write"

    async def test_calendar_read(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("what's on my calendar today", _TENANT)
        assert intent.target_service == "calendar"
        assert intent.action == "read"

    async def test_calendar_write(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("schedule a meeting tomorrow", _TENANT)
        assert intent.target_service == "calendar"
        assert intent.action == "write"

    async def test_tasks(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("show my pending tasks", _TENANT)
        assert intent.target_service == "tasks"

    async def test_general(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("hello how are you", _TENANT)
        assert intent.target_service is None
        assert intent.confidence == 0.5

    async def test_empty_string(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("", _TENANT)
        assert intent.target_service is None

    async def test_original_text_preserved(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("check my email please", _TENANT)
        assert intent.original_text == "check my email please"

    async def test_inbox_keyword(self, classifier: RegexClassifier) -> None:
        intent = await classifier.classify("show me my inbox", _TENANT)
        assert intent.target_service == "gmail"
