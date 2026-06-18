"""
Monitoring router — no auth required on /health.

Routes:
  GET /health    — uptime + version check (unlimited rate)
  GET /metrics   — aggregated Redis counters (10 req/min)
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis, limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# Track startup time for uptime calculation
_START_TIME = time.time()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="Service health check",
    tags=["Monitoring"],
    responses={200: {"description": "Service healthy"}},
)
async def health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """
    Lightweight liveness + readiness probe.
    Checks DB + Redis connectivity without exposing internals.
    Rate: unlimited (for monitoring tools — Data Security spec).
    """
    db_ok = False
    redis_ok = False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("Health DB check failed: %s", exc)

    try:
        await redis.ping()
        redis_ok = True
    except Exception as exc:
        logger.warning("Health Redis check failed: %s", exc)

    uptime_seconds = round(time.time() - _START_TIME, 1)

    status = "healthy" if (db_ok and redis_ok) else "degraded"

    return {
        "status": status,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime_seconds,
        "checks": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    summary="Aggregated service metrics from Redis counters",
    tags=["Monitoring"],
)
@limiter.limit("10/minute")   # Data Security spec: 10 req/min
async def metrics(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> dict:
    """
    Return aggregated operational metrics from Redis INCR counters.

    Keys (Technical Spec):
      metrics:orders_today   — total /order/parse calls today
      metrics:errors_today   — total 5xx errors today
      metrics:latency_sum    — cumulative processing_time_ms
      metrics:latency_count  — number of timed requests

    Average latency computed server-side.
    """
    try:
        pipe = redis.pipeline()
        pipe.get("metrics:orders_today")
        pipe.get("metrics:errors_today")
        pipe.get("metrics:latency_sum")
        pipe.get("metrics:latency_count")
        results = await pipe.execute()
    except Exception as exc:
        logger.error("Metrics Redis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Session service unavailable")

    orders_today = int(results[0] or 0)
    errors_today = int(results[1] or 0)
    latency_sum = float(results[2] or 0)
    latency_count = int(results[3] or 0)

    avg_latency_ms = round(latency_sum / latency_count, 2) if latency_count > 0 else 0.0

    return {
        "orders_today": orders_today,
        "errors_today": errors_today,
        "avg_latency_ms": avg_latency_ms,
        "total_requests": latency_count,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }
