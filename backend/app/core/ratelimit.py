"""Fixed-window rate limiter backed by Redis, with an in-process fallback if Redis is down."""
from __future__ import annotations

import logging
import threading
import time

import redis

from app.core.config import settings

log = logging.getLogger("rip.ratelimit")


class RateLimiter:
    def __init__(self, url: str):
        self._redis = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        self._local: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()
        self._redis_ok: bool | None = None

    def _local_hit(self, key: str, window: int) -> int:
        with self._lock:
            start, count = self._local.get(key, (window, 0))
            if start != window:
                start, count = window, 0
            count += 1
            self._local[key] = (start, count)
            return count

    def hit(self, key: str, limit: int, period: int = 60) -> bool:
        """Returns True when the request is allowed."""
        window = int(time.time() // period)
        rkey = f"rl:{key}:{window}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(rkey)
            pipe.expire(rkey, period + 1)
            count = int(pipe.execute()[0])
            self._redis_ok = True
        except redis.RedisError:
            if self._redis_ok is not False:
                log.warning("Redis unavailable; using in-process rate limiting")
            self._redis_ok = False
            count = self._local_hit(rkey, window)
        return count <= limit

    def healthy(self) -> bool:
        try:
            return bool(self._redis.ping())
        except redis.RedisError:
            return False


limiter = RateLimiter(settings.redis_url)
