"""
Rate limiting (tiêu chí 7) — sliding window 60 giây lưu trong Redis.
"""
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    """Kiểm tra sliding window 60s theo API key trên Redis; vượt ngưỡng trả HTTP 429."""
    if r is None:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")

    now = time.time()
    window = 60
    limit = settings.rate_limit_per_minute
    redis_key = f"ratelimit:{key}"

    try:
        r.zremrangebyscore(redis_key, 0, now - window)
        current_count = r.zcard(redis_key)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc

    if current_count >= limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window)},
        )

    member = f"{now}:{uuid.uuid4().hex}"
    try:
        r.zadd(redis_key, {member: now})
        r.expire(redis_key, window + 5)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
