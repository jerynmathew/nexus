from __future__ import annotations

from unittest.mock import patch


class TestMain:
    def test_import(self) -> None:
        import nexus

        assert hasattr(nexus, "__version__")

    def test_main_module(self) -> None:
        with patch("nexus.cli.app"):
            import runpy

            try:
                runpy.run_module("nexus", run_name="__main__", alter_sys=False)
            except SystemExit:
                pass
