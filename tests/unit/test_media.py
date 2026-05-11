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


class TestDetectMime:
    def test_jpeg(self) -> None:
        assert vision_detect_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_png(self) -> None:
        assert vision_detect_mime(b"\x89PNG\r\n\x1a\n") == "image/png"

    def test_gif(self) -> None:
        assert vision_detect_mime(b"GIF89a") == "image/gif"

    def test_unknown(self) -> None:
        assert vision_detect_mime(b"\x00\x00") == "image/jpeg"
