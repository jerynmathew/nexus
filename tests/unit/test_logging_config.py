from __future__ import annotations

import json
import logging
import sys

from nexus.logging_config import JSONFormatter, setup_logging


class TestJSONFormatter:
    def test_formats_as_json(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["msg"] == "hello world"

    def test_includes_exception(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestSetupLogging:
    def test_human_format(self) -> None:
        setup_logging(json_output=False, log_file=None)
        root = logging.getLogger()
        assert len(root.handlers) >= 1

    def test_json_format(self) -> None:
        setup_logging(json_output=True, log_file=None)
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_with_log_file(self, tmp_path) -> None:
        log_file = str(tmp_path / "test.log")
        setup_logging(json_output=False, log_file=log_file)
        root = logging.getLogger()
        assert len(root.handlers) >= 2

    def test_noisy_loggers_suppressed(self) -> None:
        setup_logging()
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("telegram").level == logging.WARNING
