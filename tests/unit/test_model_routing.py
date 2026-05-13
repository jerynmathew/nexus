from __future__ import annotations

from unittest.mock import AsyncMock

from nexus.extensions import NexusContext
from nexus.llm.client import LLMClient


class TestResolveModel:
    def test_default_model(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model() == "sonnet"

    def test_cheap_task(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model(task="CLASSIFY") == "haiku"
        assert client.resolve_model(task="SUMMARIZE") == "haiku"
        assert client.resolve_model(task="FORMAT") == "haiku"
        assert client.resolve_model(task="SKILL_EXEC") == "haiku"

    def test_skill_model_wins(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model(task="SKILL_EXEC", skill_model="gpt-4o") == "gpt-4o"

    def test_extension_model_wins_over_task(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model(task="SKILL_EXEC", extension_model="deepseek") == "deepseek"

    def test_skill_wins_over_extension(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        result = client.resolve_model(
            task="SKILL_EXEC", skill_model="gpt-4o", extension_model="deepseek"
        )
        assert result == "gpt-4o"

    def test_non_cheap_task(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model(task="CONVERSE") == "sonnet"
        assert client.resolve_model(task="BRIEFING") == "sonnet"

    def test_model_for_task_backward_compat(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.model_for_task("CLASSIFY") == "haiku"
        assert client.model_for_task("CONVERSE") == "sonnet"

    def test_case_insensitive_task(self) -> None:
        client = LLMClient(default_model="sonnet", cheap_model="haiku")
        assert client.resolve_model(task="classify") == "haiku"
        assert client.resolve_model(task="Summarize") == "haiku"


class TestRuntimeOverrides:
    def test_set_and_get(self) -> None:
        client = LLMClient()
        client.set_model_override("nexus-finance", "gpt-4o")
        assert client.get_model_override("nexus-finance") == "gpt-4o"

    def test_get_nonexistent(self) -> None:
        client = LLMClient()
        assert client.get_model_override("nothing") is None

    def test_clear(self) -> None:
        client = LLMClient()
        client.set_model_override("nexus-finance", "gpt-4o")
        client.clear_model_override("nexus-finance")
        assert client.get_model_override("nexus-finance") is None

    def test_clear_nonexistent(self) -> None:
        client = LLMClient()
        client.clear_model_override("nothing")

    def test_override_replaces(self) -> None:
        client = LLMClient()
        client.set_model_override("nexus-finance", "gpt-4o")
        client.set_model_override("nexus-finance", "llama3")
        assert client.get_model_override("nexus-finance") == "llama3"


class TestNexusContextResolveModel:
    def test_with_extension_config(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={"my-ext": {"model": "gpt-4o"}},
            extension_name="my-ext",
        )
        assert ctx.resolve_model() == "gpt-4o"

    def test_without_extension_config(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extension_name="my-ext",
        )
        assert ctx.resolve_model() == "sonnet"

    def test_cheap_task_with_no_extension_override(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extension_name="my-ext",
        )
        assert ctx.resolve_model(task="CLASSIFY") == "haiku"

    def test_extension_config_overrides_cheap_task(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={"my-ext": {"model": "gpt-4o"}},
            extension_name="my-ext",
        )
        assert ctx.resolve_model(task="CLASSIFY") == "gpt-4o"

    def test_skill_model_wins_over_extension(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={"my-ext": {"model": "gpt-4o"}},
            extension_name="my-ext",
        )
        assert ctx.resolve_model(skill_model="deepseek") == "deepseek"

    def test_runtime_override_wins_over_config(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        llm.set_model_override("my-ext", "llama3")
        ctx = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={"my-ext": {"model": "gpt-4o"}},
            extension_name="my-ext",
        )
        assert ctx.resolve_model() == "llama3"

    def test_no_llm(self) -> None:
        ctx = NexusContext(runtime=AsyncMock(), llm=None, extension_name="my-ext")
        assert ctx.resolve_model() == ""

    def test_empty_extension_name(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        ctx = NexusContext(runtime=AsyncMock(), llm=llm, extension_name="")
        assert ctx.resolve_model() == "sonnet"


class TestScopedContext:
    def test_scoped_carries_extension_name(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        root = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={"my-ext": {"model": "gpt-4o"}},
        )
        scoped = root.scoped("my-ext")
        assert scoped._extension_name == "my-ext"
        assert scoped.resolve_model() == "gpt-4o"

    def test_scoped_shares_mutable_state(self) -> None:
        root = NexusContext(runtime=AsyncMock())
        scoped = root.scoped("my-ext")
        scoped.register_command("test", AsyncMock())
        assert "test" in root.commands

    def test_scoped_shares_llm(self) -> None:
        llm = LLMClient()
        root = NexusContext(runtime=AsyncMock(), llm=llm)
        scoped = root.scoped("my-ext")
        assert scoped.llm is llm

    def test_multiple_scoped_contexts(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        root = NexusContext(
            runtime=AsyncMock(),
            llm=llm,
            extensions_config={
                "ext-a": {"model": "gpt-4o"},
                "ext-b": {"model": "llama3"},
            },
        )
        a = root.scoped("ext-a")
        b = root.scoped("ext-b")
        assert a.resolve_model() == "gpt-4o"
        assert b.resolve_model() == "llama3"

    def test_root_context_has_no_extension(self) -> None:
        llm = LLMClient(default_model="sonnet", cheap_model="haiku")
        root = NexusContext(runtime=AsyncMock(), llm=llm)
        assert root.resolve_model() == "sonnet"
