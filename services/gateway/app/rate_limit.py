"""Redis-backed fixed-window rate limiter shared across gateway replicas."""

import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError


class RateLimiterUnavailableError(Exception):
    """Raised when the limiter cannot reach Redis. The gateway fails closed in this case."""


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


class FixedWindowRateLimiter:
    """Counts requests per identity per window using an atomic INCR and EXPIRE transaction."""

    def __init__(self, redis: Redis, *, limit: int, window_seconds: int = 60, key_prefix: str = "ratelimit") -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        self._redis = redis
        self._limit = limit
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix

    async def hit(self, identity: str) -> RateLimitResult:
        now = int(time.time())
        window_index = now // self._window_seconds
        key = f"{self._key_prefix}:{identity}:{window_index}"
        try:
            async with self._redis.pipeline(transaction=True) as pipeline:
                pipeline.incr(key)
                pipeline.expire(key, self._window_seconds * 2)
                count, _ = await pipeline.execute()
        except RedisError as exc:
            raise RateLimiterUnavailableError("Rate limiter backend is unavailable") from exc

        return RateLimitResult(
            allowed=count <= self._limit,
            limit=self._limit,
            remaining=max(self._limit - count, 0),
            reset_after_seconds=self._window_seconds - (now % self._window_seconds),
        )


async def allow_within_limit(limiter: "FixedWindowRateLimiter", identity: str) -> bool:
    """Boolean adapter for the intake use cases. Fails CLOSED: if Redis is unavailable
    the request is rejected (prompt 08), never allowed through un-limited."""
    try:
        result = await limiter.hit(identity)
    except RateLimiterUnavailableError:
        return False
    return result.allowed
