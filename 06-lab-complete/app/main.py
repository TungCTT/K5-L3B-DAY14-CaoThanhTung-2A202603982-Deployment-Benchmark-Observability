"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Định dạng mỗi dòng log thành một JSON object hợp lệ."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logger() -> logging.Logger:
    log = logging.getLogger("agent")
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
    return log


logger = _configure_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý startup và graceful shutdown (uvicorn xử lý SIGTERM và gọi nhánh shutdown)."""
    logger.info(
        "agent_startup",
        extra={
            "event": "startup",
            "environment": settings.environment,
            "port": settings.port,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "daily_budget_usd": settings.daily_budget_usd,
        },
    )
    yield
    logger.info("agent_shutdown", extra={"event": "shutdown"})
    if r is not None:
        try:
            r.close()
        except Exception:
            pass


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    logger.info(
        "http_request",
        extra={
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": elapsed_ms,
        },
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        extra={
            "event": "error",
            "path": request.url.path,
            "error_type": type(exc).__name__,
        },
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


@app.get("/health")
def health():
    """Liveness probe — luôn trả 200 khi process còn sống, không phụ thuộc Redis."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    """Readiness probe — trả 200 khi Redis kết nối được, 503 khi mất kết nối."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost = record_cost(input_tokens, output_tokens)

    logger.info(
        "ask_completed",
        extra={
            "event": "ask_completed",
            "user_id": body.user_id,
            "question_len": len(body.question),
            "answer_len": len(answer),
            "cost_usd": round(cost, 6),
        },
    )
    return {"question": body.question, "answer": answer, "cost_usd": round(cost, 6)}
