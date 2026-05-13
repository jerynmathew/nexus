from __future__ import annotations

import time
from unittest.mock import patch

from nexus.ratelimit import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self) -> None:
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.check("t1") is True

    def test_blocks_over_limit(self) -> None:
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.check("t1")
        assert limiter.check("t1") is False

    def test_separate_tenants(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("t1")
        limiter.check("t1")
        assert limiter.check("t1") is False
        assert limiter.check("t2") is True

    def test_window_expiry(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.check("t1")
        limiter.check("t1")
        assert limiter.check("t1") is False

        with patch("nexus.ratelimit.time.monotonic", return_value=time.monotonic() + 2):
            assert limiter.check("t1") is True

    def test_remaining(self) -> None:
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining("t1") == 5
        limiter.check("t1")
        assert limiter.remaining("t1") == 4

    def test_reset(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("t1")
        limiter.check("t1")
        assert limiter.check("t1") is False
        limiter.reset("t1")
        assert limiter.check("t1") is True

    def test_reset_nonexistent(self) -> None:
        limiter = RateLimiter()
        limiter.reset("nobody")
