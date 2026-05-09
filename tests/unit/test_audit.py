from __future__ import annotations

import json
from pathlib import Path

from nexus.governance.audit import AuditEntry, AuditSink


class TestAuditSink:
    def test_log_creates_file(self, tmp_path: Path) -> None:
        path = str(tmp_path / "audit.jsonl")
        sink = AuditSink(path=path)
        entry = AuditEntry(
            agent="conv_manager",
            tenant_id="t1",
            tool_name="search_gmail",
            decision="ALLOW",
        )
        sink.log(entry)

        lines = Path(path).read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["agent"] == "conv_manager"
        assert parsed["tool_name"] == "search_gmail"
        assert parsed["decision"] == "ALLOW"

    def test_log_appends(self, tmp_path: Path) -> None:
        path = str(tmp_path / "audit.jsonl")
        sink = AuditSink(path=path)
        sink.log(AuditEntry(agent="a1", tool_name="t1", decision="ALLOW"))
        sink.log(AuditEntry(agent="a2", tool_name="t2", decision="DENY"))

        lines = Path(path).read_text().strip().split("\n")
        assert len(lines) == 2

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        path = str(tmp_path / "audit.jsonl")
        sink = AuditSink(path=path)
        for i in range(5):
            sink.log(AuditEntry(agent=f"a{i}", tool_name=f"t{i}", decision="ALLOW"))

        for line in Path(path).read_text().strip().split("\n"):
            parsed = json.loads(line)
            assert "agent" in parsed
            assert "timestamp" in parsed


class TestSummarizeArguments:
    def test_with_keys(self) -> None:
        result = AuditSink.summarize_arguments({"query": "test", "limit": 10})
        assert "query=..." in result

    def test_empty(self) -> None:
        result = AuditSink.summarize_arguments({})
        assert result == "(none)"
