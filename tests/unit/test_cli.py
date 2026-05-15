from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  model: test\n")

        mock_run = AsyncMock()
        with patch("nexus.cli.run_nexus", mock_run):
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

    def test_setup_default_persona(self, tmp_path: Path) -> None:
        output_path = tmp_path / "config2.yaml"
        result = runner.invoke(
            app,
            ["setup", "--output", str(output_path)],
            input="tok\nkey\nBob\n999\nUTC\n1\n",
        )
        assert result.exit_code == 0
        content = output_path.read_text()
        assert "default" in content

    def test_setup_overwrite_decline(self, tmp_path: Path) -> None:
        output_path = tmp_path / "config.yaml"
        output_path.write_text("existing")
        runner.invoke(
            app,
            ["setup", "--output", str(output_path)],
            input="n\n",
        )
        assert output_path.read_text() == "existing"


class TestSetupGoogle:
    def test_adds_credentials(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["setup-google"],
            input="client-id\nclient-secret\ntest@gmail.com\n",
        )
        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert "GOOGLE_OAUTH_CLIENT_ID=client-id" in env_content

    def test_skips_existing_vars(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("GOOGLE_OAUTH_CLIENT_ID=already\n")
        result = runner.invoke(
            app,
            ["setup-google"],
            input="new-id\nnew-secret\ntest@gmail.com\n",
        )
        assert result.exit_code == 0


class TestSetupPersona:
    def test_creates_persona(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["setup-persona"],
            input="Friday\nwitty, helpful\n2\nAlways use emoji.\n",
        )
        assert result.exit_code == 0
        persona_path = tmp_path / "personas" / "friday.md"
        assert persona_path.exists()
        content = persona_path.read_text()
        assert "Friday" in content
        assert "witty" in content


class TestPersonasCmd:
    def test_list_personas(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "dross.md").write_text("test")
        (personas_dir / "friday.md").write_text("test")
        result = runner.invoke(app, ["personas", "list"])
        assert result.exit_code == 0
        assert "dross" in result.output
        assert "friday" in result.output

    def test_list_no_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["personas", "list"])
        assert "No personas" in result.output

    def test_set_persona(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "dross.md").write_text("test")
        result = runner.invoke(app, ["personas", "set", "dross"])
        assert result.exit_code == 0
        assert "dross" in result.output

    def test_set_nonexistent(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "personas").mkdir()
        result = runner.invoke(app, ["personas", "set", "nope"])
        assert result.exit_code == 1

    def test_invalid_action(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["personas", "bogus"])
        assert "Usage" in result.output
