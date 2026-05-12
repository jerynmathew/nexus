from __future__ import annotations

from unittest.mock import AsyncMock

from nexus.media.handler import MediaHandler
from nexus.media.vision import _detect_mime as vision_detect_mime


class TestMediaHandler:
    async def test_process_voice_no_stt(self) -> None:
        handler = MediaHandler()
        result = await handler.process_voice(b"audio-data")
        assert "not configured" in result

    async def test_process_voice_with_stt(self) -> None:
        stt = AsyncMock()
        stt.transcribe.return_value = "hello world"
        handler = MediaHandler(stt=stt)
        result = await handler.process_voice(b"audio-data", "ogg")
        assert result == "hello world"
        stt.transcribe.assert_called_once_with(b"audio-data", "ogg")

    async def test_process_image_no_vision(self) -> None:
        handler = MediaHandler()
        result = await handler.process_image(b"image-data")
        assert "not configured" in result

    async def test_process_image_with_vision(self) -> None:
        vision = AsyncMock()
        vision.describe.return_value = "A cat sitting on a table"
        handler = MediaHandler(vision=vision)
        result = await handler.process_image(b"image-data", "what is this?")
        assert result == "A cat sitting on a table"

    async def test_process_document_txt(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"hello world content", "notes.txt")
        assert "hello world content" in result

    async def test_process_document_unsupported(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"\x00\x01", "binary.exe")
        assert "not supported" in result

    async def test_generate_voice_no_tts(self) -> None:
        handler = MediaHandler()
        result = await handler.generate_voice("hello")
        assert result is None

    async def test_generate_voice_with_tts(self) -> None:
        tts = AsyncMock()
        tts.synthesize.return_value = b"audio-output"
        handler = MediaHandler(tts=tts)
        result = await handler.generate_voice("hello")
        assert result == b"audio-output"


class TestMediaHandlerExtended:
    async def test_has_vision_true(self) -> None:
        handler = MediaHandler(vision=AsyncMock())
        assert handler.has_vision is True

    async def test_has_vision_false(self) -> None:
        handler = MediaHandler()
        assert handler.has_vision is False

    async def test_process_document_pdf_no_pdfplumber(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"%PDF-1.4", "report.pdf")
        assert "pdfplumber" in result or "PDF" in result

    async def test_process_document_md(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"# Title\nContent", "notes.md")
        assert "Title" in result

    async def test_process_document_csv(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"a,b,c\n1,2,3", "data.csv")
        assert "a,b,c" in result

    async def test_process_document_yaml(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"key: value", "config.yaml")
        assert "key: value" in result

    async def test_process_document_log(self) -> None:
        handler = MediaHandler()
        result = await handler.process_document(b"2026-01-01 INFO started", "app.log")
        assert "started" in result

    async def test_process_image_default_prompt(self) -> None:
        vision = AsyncMock()
        vision.describe.return_value = "An image"
        handler = MediaHandler(vision=vision)
        await handler.process_image(b"data")
        prompt = vision.describe.call_args[0][1]
        assert "Describe" in prompt

    async def test_process_video(self) -> None:
        handler = MediaHandler()
        from unittest.mock import patch

        with patch.object(handler, "_extract_video_content", return_value=("", [])):
            transcription, frames = await handler.process_video(b"video-data")
        assert transcription == ""
        assert frames == []


class TestRunFfmpeg:
    def test_file_not_found(self) -> None:
        from nexus.media.handler import _run_ffmpeg

        result = _run_ffmpeg(["-i", "/nonexistent/file.mp4", "/tmp/out.wav"])
        assert result is False


class TestExtractPdfText:
    def test_no_pdfplumber(self) -> None:
        import sys

        from nexus.media.handler import _extract_pdf_text

        saved = sys.modules.get("pdfplumber")
        sys.modules["pdfplumber"] = None
        try:
            result = _extract_pdf_text(b"%PDF-fake")
            assert "pdfplumber" in result
        finally:
            if saved is not None:
                sys.modules["pdfplumber"] = saved
            else:
                sys.modules.pop("pdfplumber", None)


class TestExtractVideoContent:
    def test_no_ffmpeg(self) -> None:
        from nexus.media.handler import MediaHandler

        handler = MediaHandler()
        transcription, frames = handler._extract_video_content(b"fake-video")
        assert transcription == ""
        assert frames == []


class TestClaudeVision:
    async def test_describe(self) -> None:
        from nexus.llm.client import LLMResponse
        from nexus.media.vision import ClaudeVision

        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="A photo of a sunset")
        vision = ClaudeVision(llm)
        result = await vision.describe(b"\xff\xd8test", "What is this?")
        assert result == "A photo of a sunset"
        llm.chat.assert_called_once()

    async def test_describe_default_prompt(self) -> None:
        from nexus.llm.client import LLMResponse
        from nexus.media.vision import ClaudeVision

        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="An image")
        vision = ClaudeVision(llm)
        await vision.describe(b"\x89PNG\r\n\x1a\ntest")
        call_msgs = llm.chat.call_args.kwargs["messages"]
        text_parts = [p for p in call_msgs[0]["content"] if p.get("type") == "text"]
        assert "Describe" in text_parts[0]["text"]


class TestDetectMime:
    def test_jpeg(self) -> None:
        assert vision_detect_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_png(self) -> None:
        assert vision_detect_mime(b"\x89PNG\r\n\x1a\n") == "image/png"

    def test_gif(self) -> None:
        assert vision_detect_mime(b"GIF89a") == "image/gif"

    def test_webp(self) -> None:
        assert vision_detect_mime(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"

    def test_unknown(self) -> None:
        assert vision_detect_mime(b"\x00\x00") == "image/jpeg"
