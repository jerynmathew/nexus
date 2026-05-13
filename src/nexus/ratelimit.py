from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import MutableMapping


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._requests: MutableMapping[str, list[float]] = defaultdict(list)

    def check(self, tenant_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        timestamps = self._requests[tenant_id]
        self._requests[tenant_id] = [t for t in timestamps if t > cutoff]

        if len(self._requests[tenant_id]) >= self._max:
            return False

        self._requests[tenant_id].append(now)
        return True

    def remaining(self, tenant_id: str) -> int:
        now = time.monotonic()
        cutoff = now - self._window
        active = [t for t in self._requests[tenant_id] if t > cutoff]
        return max(0, self._max - len(active))

    def reset(self, tenant_id: str) -> None:
        self._requests.pop(tenant_id, None)
