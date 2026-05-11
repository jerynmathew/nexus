from __future__ import annotations

import asyncio
import logging
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "small"


class WhisperSTT:
    def __init__(self, model_size: str = _DEFAULT_MODEL) -> None:
        self._model_size = model_size
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is required for STT. Install with: pip install 'nexus[voice]'"
            ) from exc

        logger.info("Loading Whisper model '%s' (first load downloads ~244MB)...", self._model_size)
        self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded")
        return self._model

    async def transcribe(self, audio_bytes: bytes, audio_format: str = "ogg") -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_bytes, audio_format)

    def _transcribe_sync(self, audio_bytes: bytes, audio_format: str) -> str:
        model = self._ensure_model()

        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            segments, _info = model.transcribe(tmp.name, beam_size=5)
            text_parts = [segment.text for segment in segments]

        transcription = " ".join(text_parts).strip()
        logger.info("Transcribed %d chars from %s audio", len(transcription), audio_format)
        return transcription
