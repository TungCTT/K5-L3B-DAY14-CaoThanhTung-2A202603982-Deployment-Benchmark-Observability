"""
Cost guard (tiêu chí 8) — theo dõi chi phí token trong Redis theo ngày.
"""
import logging
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("agent")

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _daily_cost_key() -> str:
    return f"cost:daily:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    if r is None:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")

    try:
        current = float(r.get(_daily_cost_key()) or 0.0)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc

    if current >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    )
    if r is not None:
        key = _daily_cost_key()
        try:
            r.incrbyfloat(key, cost)
            r.expire(key, 2 * 24 * 3600)
        except redis.RedisError as exc:
            logger.warning("Failed to record cost in Redis", extra={"error": str(exc)})
    return cost
