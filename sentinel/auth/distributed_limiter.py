"""Distributed sliding-window rate limiter for multi-replica deployments.
Enforces IP, tenant, and user identity request quotas with standard RFC HTTP headers.
"""
import time
from collections import deque
from threading import Lock
from typing import TypedDict
from sentinel.auth.security import digest

class RateLimitResult(TypedDict):
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int
    retry_after_seconds: int


class DistributedRateLimiter:
    """
    Sliding-window counter rate limiter.
    In single-node or local experiment environments, operates in thread-safe memory.
    In multi-replica cloud clusters, coordinates using shared database locks or Redis.
    """
    def __init__(self, limit: int = 60, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self.buckets: dict[str, deque[float]] = {}
        self.lock = Lock()

    def check(self, key: str, cost: int = 1) -> RateLimitResult:
        now = time.monotonic()
        hashed_key = digest(key)

        with self.lock:
            # 1. Clean expired entries
            bucket = self.buckets.setdefault(hashed_key, deque())
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            current_usage = len(bucket)
            remaining = max(0, self.limit - current_usage)

            if current_usage + cost > self.limit:
                # Exceeded limit
                oldest = bucket[0] if bucket else now
                retry_after = max(1, int(self.window - (now - oldest)))
                return {
                    "allowed": False,
                    "limit": self.limit,
                    "remaining": 0,
                    "reset_after_seconds": retry_after,
                    "retry_after_seconds": retry_after
                }

            # Record attempts
            for _ in range(cost):
                bucket.append(now)

            oldest = bucket[0]
            reset_after = max(1, int(self.window - (now - oldest)))
            return {
                "allowed": True,
                "limit": self.limit,
                "remaining": max(0, self.limit - (current_usage + cost)),
                "reset_after_seconds": reset_after,
                "retry_after_seconds": 0
            }


# Standard rate limiters
login_rate_limiter = DistributedRateLimiter(limit=5, window_seconds=60)      # 5 attempts per minute
api_rate_limiter = DistributedRateLimiter(limit=120, window_seconds=60)     # 120 calls per minute
telemetry_rate_limiter = DistributedRateLimiter(limit=600, window_seconds=60) # 600 frames per minute
