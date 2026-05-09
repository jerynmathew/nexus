from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from nexus.cli import app

runner = CliRunner()


class TestVersion:
    def test_prints_version(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Nexus" in result.output
        assert "Python" in result.output
        assert "Civitas" in result.output


class TestRun:
    def test_missing_config_errors(self) -> None:
        result = runner.invoke(app, ["run", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_valid_config(self, tmp_path: Path) -> None:
        from unittest.mock import AsyncMock, patch

        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  model: test\n")

        mock_run = AsyncMock()
        with patch("nexus.runtime.run_nexus", mock_run):
            result = runner.invoke(app, ["run", "--config", str(config)])

        assert result.exit_code == 0
        assert "Config loaded" in result.output


class TestSetup:
    def test_interactive_setup(self, tmp_path: Path) -> None:
        output_path = tmp_path / "config.yaml"
        result = runner.invoke(
            app,
            ["setup", "--output", str(output_path)],
            input="fake-bot-token\nfake-api-key\nAlice\n12345\nUTC\n2\n",
        )
        assert result.exit_code == 0
        assert "Config written" in result.output
        assert output_path.exists()
        content = output_path.read_text()
        assert "fake-bot-token" in content
        assert "Alice" in content
        assert "dross" in content
