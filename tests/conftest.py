from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_config() -> None:
    """Reset config singleton between tests to prevent leakage."""
    yield
