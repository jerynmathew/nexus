from __future__ import annotations

from nexus.transport.telegram import TelegramTransport, _markdown_to_html


class TestMarkdownToHtml:
    def test_bold(self) -> None:
        assert "<b>bold</b>" in _markdown_to_html("**bold**")

    def test_italic_star(self) -> None:
        assert "<i>italic</i>" in _markdown_to_html("*italic*")

    def test_italic_underscore(self) -> None:
        assert "<i>italic</i>" in _markdown_to_html("_italic_")

    def test_code_inline(self) -> None:
        assert "<code>code</code>" in _markdown_to_html("`code`")

    def test_code_block(self) -> None:
        result = _markdown_to_html("```python\nprint('hi')\n```")
        assert "<pre>" in result
        assert "print" in result

    def test_link(self) -> None:
        result = _markdown_to_html("[Google](https://google.com)")
        assert '<a href="https://google.com">Google</a>' in result

    def test_html_entities_escaped(self) -> None:
        result = _markdown_to_html("1 < 2 & 3 > 0")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_plain_text_unchanged(self) -> None:
        assert _markdown_to_html("hello world") == "hello world"

    def test_mixed_formatting(self) -> None:
        result = _markdown_to_html("**bold** and *italic* and `code`")
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert "<code>code</code>" in result


class TestSplitMessage:
    def test_short_message(self) -> None:
        chunks = TelegramTransport._split_message("short")
        assert chunks == ["short"]

    def test_long_message_splits_on_newline(self) -> None:
        lines = [f"Line {i}" for i in range(1000)]
        text = "\n".join(lines)
        chunks = TelegramTransport._split_message(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 4096

    def test_no_empty_chunks(self) -> None:
        text = "a\n" * 5000
        chunks = TelegramTransport._split_message(text)
        for chunk in chunks:
            assert chunk.strip()
