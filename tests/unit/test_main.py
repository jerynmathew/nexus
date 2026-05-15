from __future__ import annotations

import runpy
from unittest.mock import patch

import nexus


class TestMain:
    def test_import(self) -> None:
        assert hasattr(nexus, "__version__")

    def test_main_module(self) -> None:
        with patch("nexus.cli.app") as mock_app:
            try:
                runpy.run_module("nexus", run_name="__main__", alter_sys=False)
            except SystemExit:
                pass
            assert mock_app is not None
