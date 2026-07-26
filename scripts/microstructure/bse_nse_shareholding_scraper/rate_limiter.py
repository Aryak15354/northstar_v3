#!/usr/bin/env python3
"""Thread-safe token-bucket rate limiter, shared across all worker threads.

A global limiter (not one per thread) is the point: `--workers 8 --qps 2` means the whole scrape
never exceeds 2 requests/second combined, however many threads are running -- concurrency here buys
latency-hiding (overlapping the wait time of slow responses), not higher request volume against the
exchange's servers.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, qps: float, burst: float | None = None):
        if qps <= 0:
            raise ValueError(f"qps must be > 0, got {qps}")
        self.rate = float(qps)
        self.capacity = float(burst if burst is not None else max(qps, 1.0))
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self.rate
            time.sleep(wait)


class CircuitBreaker:
    """Trips after N consecutive failures; the caller should stop and let a wrapper cool down and
    re-bootstrap a session, mirroring the working pattern in fetch_nse_microstructure.py's own
    max-consec-fail circuit breaker."""

    def __init__(self, max_consecutive_failures: int = 8):
        self.max_consecutive_failures = int(max_consecutive_failures)
        self._consec = 0
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self._consec = 0

    def record_failure(self) -> bool:
        """Returns True if the breaker has now tripped."""
        with self._lock:
            self._consec += 1
            return self._consec >= self.max_consecutive_failures

    @property
    def tripped(self) -> bool:
        with self._lock:
            return self._consec >= self.max_consecutive_failures
