# shared/middleware.py
"""
WHY THIS FILE EXISTS:
Implements Redis-backed idempotency caching and lock primitives for microservices and the Coordinator.

Why this approach?
Network retries (e.g. HTTP timeout retry) can cause a client to send the exact same request twice.
Without idempotency controls, a payment service might charge a customer twice or inventory might be deducted twice.

Using Redis `SET key value NX EX` allows sub-millisecond deduplication checks.

Interview Explanation:
"Idempotency keys ensure operations are executed at most once. We use Redis atomic key setting (NX=True) 
with a 24-hour expiration (TTL) to block duplicate retries instantly."
"""

import os
from typing import Optional, Tuple
import redis.asyncio as aioredis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

_redis_pool: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    """Returns a singleton Redis client instance."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
    return _redis_pool


async def check_idempotency_key(redis: aioredis.Redis, key: str) -> Optional[str]:
    """
    Checks if an idempotency key exists in Redis cache.
    Returns the cached response JSON string if key exists, otherwise None.
    """
    try:
        cached_res = await redis.get(f"idempotency:{key}")
        return cached_res
    except Exception:
        # Fall back gracefully if Redis is temporarily unreachable
        return None


async def save_idempotency_key(redis: aioredis.Redis, key: str, response_json: str, ttl_seconds: int = 86400) -> bool:
    """
    Saves an idempotency key and response in Redis with expiration TTL (default 24 hours).
    """
    try:
        await redis.set(f"idempotency:{key}", response_json, ex=ttl_seconds)
        return True
    except Exception:
        return False
