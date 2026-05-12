from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from nexus.media.stt import WhisperSTT


class TestInit:
    def test_default_model_size(self) -> None:
        stt = WhisperSTT()
        assert stt._model_size == "small"
        assert stt._model is None

    def test_custom_model_size(self) -> None:
        stt = WhisperSTT(model_size="tiny")
        assert stt._model_size == "tiny"


class TestEnsureModel:
    def test_import_error(self) -> None:
        stt = WhisperSTT()
        with patch("nexus.media.stt._HAS_FASTER_WHISPER", False):
            with pytest.raises(RuntimeError, match="faster-whisper"):
                stt._ensure_model()

    def test_loads_once(self) -> None:
        stt = WhisperSTT()
        mock_model = MagicMock()
        with (
            patch("nexus.media.stt._HAS_FASTER_WHISPER", True),
            patch("nexus.media.stt.WhisperModel", create=True, return_value=mock_model),
        ):
            result1 = stt._ensure_model()
            result2 = stt._ensure_model()
        assert result1 is mock_model
        assert result2 is mock_model


class TestTranscribeSync:
    def test_joins_segments(self) -> None:
        stt = WhisperSTT()
        mock_model = MagicMock()
        segments = [
            SimpleNamespace(text=" Hello"),
            SimpleNamespace(text=" world"),
        ]
        mock_model.transcribe.return_value = (segments, MagicMock())
        stt._model = mock_model

        result = stt._transcribe_sync(b"audio-data", "ogg")
        assert "Hello" in result
        assert "world" in result


class TestTranscribe:
    async def test_delegates_to_executor(self) -> None:
        stt = WhisperSTT()
        mock_model = MagicMock()
        segments = [SimpleNamespace(text=" test")]
        mock_model.transcribe.return_value = (segments, MagicMock())
        stt._model = mock_model

        result = await stt.transcribe(b"audio", "wav")
        assert result == "test"
