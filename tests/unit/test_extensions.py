from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch as _patch

from nexus.extensions import (
    ExtensionLoader,
    NexusContext,
    NexusExtension,
    _DirectoryExtension,
)

_NO_ENTRY_POINTS = _patch("nexus.extensions.entry_points", return_value=[])


class _FakeExtension:
    @property
    def name(self) -> str:
        return "test-ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def on_load(self, nexus: NexusContext) -> None:
        nexus.register_command("test", AsyncMock())
        nexus.register_schema("CREATE TABLE IF NOT EXISTS test (id INTEGER);")

    async def on_unload(self) -> None:
        pass


class TestNexusExtensionProtocol:
    def test_fake_extension_is_protocol_compatible(self) -> None:
        ext = _FakeExtension()
        assert isinstance(ext, NexusExtension)


class TestNexusContext:
    def test_register_command(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        handler = AsyncMock()
        ctx.register_command("portfolio", handler)
        assert "portfolio" in ctx.commands
        assert ctx.commands["portfolio"] is handler

    def test_duplicate_command_skipped(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        first = AsyncMock()
        second = AsyncMock()
        ctx.register_command("test", first)
        ctx.register_command("test", second)
        assert ctx.commands["test"] is first

    def test_register_schema(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        ctx.register_schema("CREATE TABLE t (id INT);")
        ctx.register_schema("CREATE TABLE t2 (id INT);")
        assert len(ctx.schemas) == 2

    def test_register_skill_dir_exists(self, tmp_path: Path) -> None:
        ctx = NexusContext(runtime=MagicMock())
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        ctx.register_skill_dir(skill_dir)
        assert skill_dir in ctx.skill_dirs

    def test_register_skill_dir_missing(self, tmp_path: Path) -> None:
        ctx = NexusContext(runtime=MagicMock())
        ctx.register_skill_dir(tmp_path / "nonexistent")
        assert len(ctx.skill_dirs) == 0

    def test_register_signal_handler(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        handler = AsyncMock()
        ctx.register_signal_handler("inbound_message", handler)
        assert len(ctx.signal_handlers["inbound_message"]) == 1

    def test_register_hook(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        handler = AsyncMock()
        ctx.register_hook("pre_message", handler)
        assert len(ctx.hooks["pre_message"]) == 1

    def test_get_config_present(self) -> None:
        ctx = NexusContext(
            runtime=MagicMock(),
            extensions_config={"nexus-finance": {"api_key": "test"}},
        )
        cfg = ctx.get_config("nexus-finance")
        assert cfg["api_key"] == "test"

    def test_get_config_missing(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        assert ctx.get_config("nonexistent") == {}

    async def test_send_to_memory(self) -> None:
        runtime = AsyncMock()
        runtime.call.return_value = {"status": "ok"}
        ctx = NexusContext(runtime=runtime)
        result = await ctx.send_to_memory("store", {"key": "val"})
        runtime.call.assert_called_once_with("memory", {"action": "store", "key": "val"})
        assert result["status"] == "ok"

    async def test_send_to_dashboard(self) -> None:
        runtime = AsyncMock()
        ctx = NexusContext(runtime=runtime)
        await ctx.send_to_dashboard("activity", {"type": "test"})
        runtime.cast.assert_called_once()

    def test_llm_property(self) -> None:
        llm = MagicMock()
        ctx = NexusContext(runtime=MagicMock(), llm=llm)
        assert ctx.llm is llm

    def test_llm_none(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        assert ctx.llm is None


class TestExtensionLoader:
    @_NO_ENTRY_POINTS
    async def test_load_no_extensions(self, _mock_ep: MagicMock) -> None:
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        result = await loader.load_all()
        assert result == []

    async def test_unload_all(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        ext = _FakeExtension()
        loader._extensions.append(ext)
        await loader.unload_all()
        assert loader.extensions == []

    async def test_unload_error_suppressed(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        ext = MagicMock()
        ext.name = "bad"
        ext.on_unload = AsyncMock(side_effect=Exception("fail"))
        loader._extensions.append(ext)
        await loader.unload_all()
        assert loader.extensions == []

    @_NO_ENTRY_POINTS
    async def test_load_directory_extension(self, _mock_ep: MagicMock, tmp_path: Path) -> None:
        ext_dir = tmp_path / "my-ext"
        ext_dir.mkdir()
        skills_dir = ext_dir / "skills"
        skills_dir.mkdir()
        manifest = ext_dir / "extension.yaml"
        manifest.write_text("name: my-ext\nversion: 1.0.0\n")

        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        await loader.load_all(extension_dirs=[tmp_path])
        assert len(loader.extensions) == 1
        assert loader.extensions[0].name == "my-ext"
        assert skills_dir in ctx.skill_dirs

    @_NO_ENTRY_POINTS
    async def test_load_directory_no_manifest(self, _mock_ep: MagicMock, tmp_path: Path) -> None:
        ext_dir = tmp_path / "no-manifest"
        ext_dir.mkdir()
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        await loader.load_all(extension_dirs=[tmp_path])
        assert len(loader.extensions) == 0

    @_NO_ENTRY_POINTS
    async def test_load_directory_invalid_manifest(
        self, _mock_ep: MagicMock, tmp_path: Path
    ) -> None:
        ext_dir = tmp_path / "bad-ext"
        ext_dir.mkdir()
        (ext_dir / "extension.yaml").write_text("not a mapping")
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        await loader.load_all(extension_dirs=[tmp_path])
        assert len(loader.extensions) == 0

    @_NO_ENTRY_POINTS
    async def test_load_nonexistent_dir(self, _mock_ep: MagicMock) -> None:
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        await loader.load_all(extension_dirs=[Path("/nonexistent")])
        assert len(loader.extensions) == 0

    def test_extensions_property(self) -> None:
        ctx = NexusContext(runtime=MagicMock())
        loader = ExtensionLoader(ctx)
        ext = _FakeExtension()
        loader._extensions.append(ext)
        assert len(loader.extensions) == 1
        assert loader.extensions[0] is ext


class TestDirectoryExtension:
    def test_name_from_manifest(self) -> None:
        ext = _DirectoryExtension({"name": "my-ext", "version": "2.0"}, Path("/tmp"))
        assert ext.name == "my-ext"
        assert ext.version == "2.0"

    def test_name_fallback_to_dir(self) -> None:
        ext = _DirectoryExtension({}, Path("/tmp/my-dir"))
        assert ext.name == "my-dir"
        assert ext.version == "0.0.0"

    async def test_on_load_with_skills(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        ext = _DirectoryExtension({"name": "test"}, tmp_path)
        ctx = NexusContext(runtime=MagicMock())
        await ext.on_load(ctx)
        assert skills_dir in ctx.skill_dirs

    async def test_on_load_no_skills_dir(self, tmp_path: Path) -> None:
        ext = _DirectoryExtension({"name": "test"}, tmp_path)
        ctx = NexusContext(runtime=MagicMock())
        await ext.on_load(ctx)
        assert len(ctx.skill_dirs) == 0

    async def test_on_unload(self) -> None:
        ext = _DirectoryExtension({"name": "test"}, Path("/tmp"))
        await ext.on_unload()


class TestConversationExtCommands:
    async def test_ext_command_dispatched(self) -> None:
        from civitas.messages import Message

        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        handler = AsyncMock()
        conv.register_ext_commands({"portfolio": handler})
        conv._transport = AsyncMock()

        msg = Message(
            sender="test",
            recipient="test",
            payload={
                "action": "command",
                "command": "portfolio",
                "args": "",
                "tenant_id": "t1",
                "channel_id": "c1",
            },
            reply_to="test",
        )
        await conv._handle_command(msg)
        handler.assert_called_once()
        kwargs = handler.call_args.kwargs
        assert kwargs["command"] == "portfolio"
        assert kwargs["tenant_id"] == "t1"

    async def test_ext_command_not_found_falls_through(self) -> None:
        from civitas.messages import Message

        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        conv._transport = AsyncMock()

        msg = Message(
            sender="test",
            recipient="test",
            payload={
                "action": "command",
                "command": "bogus",
                "args": "",
                "tenant_id": "t1",
                "channel_id": "c1",
            },
            reply_to="test",
        )
        await conv._handle_command(msg)
        sent = conv._transport.send_text.call_args[0][1]
        assert "Unknown command" in sent


class TestConversationSignalHandlers:
    async def test_fire_signal_handlers(self) -> None:
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        conv.register_ext_signal_handlers({"inbound_message": [handler1, handler2]})
        await conv._fire_signal_handlers("inbound_message", {"text": "hi"})
        handler1.assert_called_once_with({"text": "hi"})
        handler2.assert_called_once_with({"text": "hi"})

    async def test_fire_signal_handler_error_suppressed(self) -> None:
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        bad_handler = AsyncMock(side_effect=Exception("fail"))
        good_handler = AsyncMock()
        conv.register_ext_signal_handlers({"test": [bad_handler, good_handler]})
        await conv._fire_signal_handlers("test", {})
        good_handler.assert_called_once()

    async def test_no_handlers_for_event(self) -> None:
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        await conv._fire_signal_handlers("nonexistent", {})


class TestMemorySchemaRegistration:
    async def test_extension_schema_executed(self) -> None:
        from nexus.agents.memory import MemoryAgent

        mem = MemoryAgent(name="memory", db_path=":memory:")
        mem.register_extension_schemas(
            ["CREATE TABLE IF NOT EXISTS ext_test (id INTEGER PRIMARY KEY, val TEXT);"]
        )
        await mem.on_start()
        assert mem._db is not None
        async with mem._db.execute("SELECT name FROM sqlite_master WHERE name='ext_test'") as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row[0] == "ext_test"
        await mem.on_stop()


class TestSkillManagerDynamicDirs:
    def test_add_skill_dir(self, tmp_path: Path) -> None:
        from nexus.skills.manager import SkillManager

        mgr = SkillManager(tmp_path / "base")
        extra = tmp_path / "extra"
        extra.mkdir()
        mgr.add_skill_dir(extra)
        assert extra in mgr._extra_dirs

    def test_add_skill_dir_no_duplicate(self, tmp_path: Path) -> None:
        from nexus.skills.manager import SkillManager

        mgr = SkillManager(tmp_path / "base")
        extra = tmp_path / "extra"
        extra.mkdir()
        mgr.add_skill_dir(extra)
        mgr.add_skill_dir(extra)
        assert mgr._extra_dirs.count(extra) == 1

    def test_load_all_includes_extra_dirs(self, tmp_path: Path) -> None:
        from nexus.skills.manager import SkillManager

        base = tmp_path / "base"
        base.mkdir()
        extra = tmp_path / "extra"
        extra.mkdir()
        skill_dir = extra / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test\n---\nDo the thing."
        )

        mgr = SkillManager(base)
        mgr.add_skill_dir(extra)
        mgr.load_all()
        assert mgr.get("test-skill") is not None

    def test_add_after_loaded_triggers_scan(self, tmp_path: Path) -> None:
        from nexus.skills.manager import SkillManager

        base = tmp_path / "base"
        base.mkdir()
        mgr = SkillManager(base)
        mgr.load_all()
        assert mgr._loaded is True

        extra = tmp_path / "extra"
        extra.mkdir()
        skill_dir = extra / "late-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: late-skill\ndescription: Added late\n---\nDo it."
        )
        mgr.add_skill_dir(extra)
        assert mgr.get("late-skill") is not None
