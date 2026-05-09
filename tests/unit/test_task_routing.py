from __future__ import annotations

from nexus.llm.client import LLMClient


class TestModelForTask:
    async def test_classify_uses_cheap_model(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("CLASSIFY") == "haiku"
        await client.close()

    async def test_summarize_uses_cheap_model(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("SUMMARIZE") == "haiku"
        await client.close()

    async def test_format_uses_cheap_model(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("FORMAT") == "haiku"
        await client.close()

    async def test_skill_exec_uses_cheap_model(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("SKILL_EXEC") == "haiku"
        await client.close()

    async def test_converse_uses_primary_model(self) -> None:
        client = LLMClient(
            base_url="http://localhost:9999",
            default_model="sonnet",
        )
        assert client.model_for_task("CONVERSE") == "sonnet"
        await client.close()

    async def test_unknown_task_uses_primary(self) -> None:
        client = LLMClient(
            base_url="http://localhost:9999",
            default_model="sonnet",
        )
        assert client.model_for_task("UNKNOWN") == "sonnet"
        await client.close()

    async def test_case_insensitive(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("classify") == "haiku"
        await client.close()
