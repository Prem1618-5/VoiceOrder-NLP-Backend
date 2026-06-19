"""
Monitoring router — no JWT required on either endpoint.

Routes:
  GET /health    Uptime, version, DB + Redis connectivity (unlimited)
  GET /metrics   Aggregated Redis counters — rate-limited 10 req/min
"""
import logging
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, limiter

logger = logging.getLogger(__name__)
router = APIRouter()

_STARTUP_TIME: float = time.time()
APP_VERSION = "1.0.0"


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="Health check — no auth required, unlimited",
    tags=["monitoring"],
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    Returns overall service health and individual component status.
    Used by Railway health-check and external monitoring tools.
    HTTP 200 always — callers should inspect `status` field.
    """
    checks: dict = {"db": False, "redis": False}

    # Database connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception as exc:
        logger.warning("Health check — DB unreachable: %s", exc)

    # Redis connectivity
    try:
        await redis.ping()
        checks["redis"] = True
    except Exception as exc:
        logger.warning("Health check — Redis unreachable: %s", exc)

    overall_status = "ok" if all(checks.values()) else "degraded"
    uptime_seconds = round(time.time() - _STARTUP_TIME, 1)

    return {
        "status": overall_status,
        "version": APP_VERSION,
        "uptime_seconds": uptime_seconds,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── GET /metrics ──────────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    summary="Operational metrics (10 req/min, no auth)",
    tags=["monitoring"],
    responses={
        503: {"description": "Redis unavailable — metrics cannot be retrieved"},
    },
)
@limiter.limit("10/minute")
async def metrics(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    Return aggregated operational metrics sourced from Redis INCR counters.

    Counter keys (incremented by the orders router):
      metrics:orders_today    — total /order/parse calls today
      metrics:errors_today    — total 5xx responses today
      metrics:latency_sum     — sum of processing_time_ms across all parses
      metrics:latency_count   — number of parse calls (denominator for avg)
      metrics:for_review_today — parses flagged for human review

    Returns 503 with a safe message if Redis is unavailable
    (Data Security spec: "Redis timeout → 'Session service unavailable'").
    """
    try:
        orders_today   = int(await redis.get("metrics:orders_today")    or 0)
        errors_today   = int(await redis.get("metrics:errors_today")    or 0)
        latency_sum    = float(await redis.get("metrics:latency_sum")   or 0.0)
        latency_count  = int(await redis.get("metrics:latency_count")   or 0)
        for_review     = int(await redis.get("metrics:for_review_today") or 0)

        avg_latency_ms = (
            round(latency_sum / latency_count, 2) if latency_count > 0 else 0.0
        )
        error_rate = (
            round(errors_today / orders_today, 4) if orders_today > 0 else 0.0
        )

        return {
            "orders_today": orders_today,
            "errors_today": errors_today,
            "for_review_today": for_review,
            "avg_latency_ms": avg_latency_ms,
            "error_rate": error_rate,
            "uptime_seconds": round(time.time() - _STARTUP_TIME, 1),
        }

    except Exception as exc:
        logger.error("Metrics retrieval failed: %s", exc, exc_info=True)
        # Data Security spec: safe error message, no internals
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Session service unavailable",
                "code": "METRICS_UNAVAILABLE",
            },
        )
