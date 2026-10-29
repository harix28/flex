"""Bounded, thread-safe process-local limits. Shared enforcement needed for replicas."""
from collections import deque
from threading import Lock
from time import monotonic
from .security import digest

class LoginLimiter:
    def __init__(self, limit, window, global_limit):
        self.limit, self.window, self.global_limit = limit, window, global_limit
        self.buckets = {}
        self.lock = Lock()

    def allow(self, address, email):
        now = monotonic()
        keys = [('global', self.global_limit), ('ip:' + digest(address), self.limit),
                ('email:' + digest(email), self.limit)]
        with self.lock:
            for key in list(self.buckets):
                bucket = self.buckets[key]
                while bucket and bucket[0] <= now - self.window:
                    bucket.popleft()
                if not bucket:
                    del self.buckets[key]
            if len(self.buckets) >= 10000:
                return False
            if any(len(self.buckets.get(key, ())) >= limit for key, limit in keys):
                return False
            for key, _ in keys:
                self.buckets.setdefault(key, deque()).append(now)
            return True
