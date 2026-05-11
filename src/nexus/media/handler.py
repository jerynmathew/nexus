from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class STTProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, audio_format: str = "ogg") -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, text: str, voice_ref: bytes | None = None) -> bytes: ...


@runtime_checkable
class VisionProvider(Protocol):
    async def describe(self, image_bytes: bytes, prompt: str = "") -> str: ...


class MediaHandler:
    def __init__(
        self,
        stt: STTProvider | None = None,
        tts: TTSProvider | None = None,
        vision: VisionProvider | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._vision = vision

    async def process_voice(self, audio_bytes: bytes, audio_format: str = "ogg") -> str:
        if not self._stt:
            return "[Voice message received but STT is not configured]"
        return await self._stt.transcribe(audio_bytes, audio_format)

    async def process_image(self, image_bytes: bytes, caption: str = "") -> str:
        if not self._vision:
            return "[Image received but vision is not configured]"
        prompt = caption or "Describe this image in detail."
        return await self._vision.describe(image_bytes, prompt)

    async def process_document(self, doc_bytes: bytes, filename: str) -> str:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return await self._parse_pdf(doc_bytes)
        if lower.endswith((".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log")):
            return doc_bytes.decode(errors="replace")[:50_000]
        return f"[Document '{filename}' received but format not supported for parsing]"

    async def process_video(self, video_bytes: bytes) -> tuple[str, list[bytes]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_video_content, video_bytes)

    async def generate_voice(self, text: str, voice_ref: bytes | None = None) -> bytes | None:
        if not self._tts:
            return None
        return await self._tts.synthesize(text, voice_ref)

    @staticmethod
    async def _parse_pdf(pdf_bytes: bytes) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _extract_pdf_text, pdf_bytes)

    @staticmethod
    def _extract_video_content(video_bytes: bytes) -> tuple[str, list[bytes]]:
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "input.mp4"
            video_path.write_bytes(video_bytes)

            audio_path = Path(tmp) / "audio.wav"
            _run_ffmpeg(
                [
                    "-i",
                    str(video_path),
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(audio_path),
                ]
            )
            audio_data = audio_path.read_bytes() if audio_path.exists() else b""

            frames: list[bytes] = []
            frame_dir = Path(tmp) / "frames"
            frame_dir.mkdir()
            _run_ffmpeg(
                [
                    "-i",
                    str(video_path),
                    "-vf",
                    "fps=1,scale=512:-1",
                    "-frames:v",
                    "5",
                    str(frame_dir / "frame_%03d.jpg"),
                ]
            )
            for frame_file in sorted(frame_dir.glob("*.jpg")):
                frames.append(frame_file.read_bytes())

            transcription = ""
            if audio_data:
                transcription = f"[Audio extracted: {len(audio_data)} bytes]"

            return transcription, frames


def _run_ffmpeg(args: list[str]) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *args],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("ffmpeg command failed: %s", " ".join(args))
        return False


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return (
            "[PDF received but pdfplumber is not installed. Install with: pip install nexus[docs]]"
        )

    import io

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:50]:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    return full_text[:50_000]
