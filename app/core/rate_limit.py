from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """Small in-process sliding-window limiter.

    Sufficient for the single-process capstone deployment (see docs/architecture.md);
    a multi-process deployment would need a shared store.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Record a hit. Returns None when allowed, else the seconds until the caller may retry."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                return max(1, int(self.window_seconds - (now - hits[0])) + 1)
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


auth_rate_limiter = SlidingWindowRateLimiter(settings.auth_rate_limit_attempts, settings.auth_rate_limit_window_seconds)


def limit_auth_attempts(request: Request) -> None:
    """FastAPI dependency throttling credential endpoints per client address and route."""
    client = request.client.host if request.client else "unknown"
    retry_after = auth_rate_limiter.check(f"{client}:{request.url.path}")
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts; try again later",
            headers={"Retry-After": str(retry_after)},
        )
