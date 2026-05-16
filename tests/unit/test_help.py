from __future__ import annotations

from unittest.mock import MagicMock

from nexus.agents.help import build_capabilities_section, build_help_response, is_help_query


class TestIsHelpQuery:
    def test_help_keyword(self) -> None:
        assert is_help_query("help") is True

    def test_help_in_sentence(self) -> None:
        assert is_help_query("I need help") is True

    def test_slash_help(self) -> None:
        assert is_help_query("/help") is True

    def test_what_commands(self) -> None:
        assert is_help_query("what commands") is True

    def test_what_can_you_do(self) -> None:
        assert is_help_query("what can you do") is True

    def test_available_commands(self) -> None:
        assert is_help_query("available commands") is True

    def test_list_commands(self) -> None:
        assert is_help_query("list commands") is True

    def test_show_commands(self) -> None:
        assert is_help_query("show commands") is True

    def test_case_insensitive(self) -> None:
        assert is_help_query("HELP") is True

    def test_non_help_query(self) -> None:
        assert is_help_query("hello") is False

    def test_unrelated_text(self) -> None:
        assert is_help_query("what is the weather today") is False

    def test_empty_string(self) -> None:
        assert is_help_query("") is False


class TestBuildHelpResponse:
    def test_no_ext_commands_system_section_present(self) -> None:
        result = build_help_response({})
        assert "**System**" in result
        assert "/status" in result

    def test_no_ext_commands_work_section_empty(self) -> None:
        result = build_help_response({})
        assert "/actions" not in result
        assert "/delegate" not in result
        assert "/meetings" not in result
        assert "/next" not in result

    def test_no_ext_commands_finance_section_empty(self) -> None:
        result = build_help_response({})
        assert "/portfolio" not in result
        assert "/fire" not in result

    def test_work_commands_populate_work_section(self) -> None:
        ext = {"actions": object(), "delegate": object()}
        result = build_help_response(ext)
        assert "**Work**" in result
        assert "/actions" in result
        assert "Manage action items" in result
        assert "/delegate" in result
        assert "Track delegations" in result

    def test_finance_commands_populate_finance_section(self) -> None:
        ext = {"portfolio": object(), "fire": object()}
        result = build_help_response(ext)
        assert "**Finance**" in result
        assert "/portfolio" in result
        assert "Portfolio summary" in result
        assert "/fire" in result
        assert "FIRE progress" in result

    def test_all_commands_all_sections_populated(self) -> None:
        ext = {
            "actions": object(),
            "delegate": object(),
            "meetings": object(),
            "next": object(),
            "portfolio": object(),
            "fire": object(),
            "rebalance": object(),
            "research": object(),
            "gold": object(),
            "holdings": object(),
        }
        result = build_help_response(ext)
        assert "**Work**" in result
        assert "**Finance**" in result
        assert "**System**" in result
        assert "/actions" in result
        assert "/portfolio" in result
        assert "/status" in result

    def test_natural_language_footer_always_present(self) -> None:
        result = build_help_response({})
        assert "natural language" in result

    def test_available_commands_header(self) -> None:
        result = build_help_response({})
        assert "**Available Commands**" in result


class TestBuildCapabilitiesSection:
    def test_no_ext_commands_no_slash_commands_listed(self) -> None:
        result = build_capabilities_section({}, mcp=None, media_handler=None)
        assert "User Slash Commands" not in result

    def test_ext_commands_lists_sorted_slash_commands(self) -> None:
        ext = {"portfolio": object(), "actions": object(), "fire": object()}
        result = build_capabilities_section(ext, mcp=None, media_handler=None)
        assert "User Slash Commands" in result
        assert "/actions" in result
        assert "/portfolio" in result
        assert "/fire" in result
        actions_pos = result.index("/actions")
        fire_pos = result.index("/fire")
        portfolio_pos = result.index("/portfolio")
        assert actions_pos < fire_pos < portfolio_pos

    def test_ext_commands_with_known_description(self) -> None:
        ext = {"actions": object()}
        result = build_capabilities_section(ext, mcp=None, media_handler=None)
        assert "Manage action items" in result

    def test_ext_commands_without_known_description(self) -> None:
        ext = {"custom_cmd": object()}
        result = build_capabilities_section(ext, mcp=None, media_handler=None)
        assert "/custom_cmd" in result

    def test_mcp_with_tools(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = [{"name": "tool1"}, {"name": "tool2"}]
        result = build_capabilities_section({}, mcp=mcp, media_handler=None)
        assert "2 tools available via MCP" in result

    def test_mcp_no_tools(self) -> None:
        mcp = MagicMock()
        mcp.all_tool_schemas.return_value = []
        result = build_capabilities_section({}, mcp=mcp, media_handler=None)
        assert "No MCP tools currently connected" in result

    def test_no_mcp(self) -> None:
        result = build_capabilities_section({}, mcp=None, media_handler=None)
        assert "No MCP connection" in result

    def test_media_handler_with_vision(self) -> None:
        handler = MagicMock()
        handler.has_vision = True
        result = build_capabilities_section({}, mcp=None, media_handler=handler)
        assert "analyze images" in result

    def test_no_media_handler(self) -> None:
        result = build_capabilities_section({}, mcp=None, media_handler=None)
        assert "Voice and image processing are not available" in result

    def test_formatting_section_always_present(self) -> None:
        result = build_capabilities_section({}, mcp=None, media_handler=None)
        assert "## Formatting" in result
        assert "markdown" in result

    def test_capabilities_header(self) -> None:
        result = build_capabilities_section({}, mcp=None, media_handler=None)
        assert "# Available Capabilities" in result
