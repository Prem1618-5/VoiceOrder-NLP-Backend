"""
VoiceOrder NLP Backend — FastAPI application entry point.

Initialises:
  • CORS (strict in prod, permissive in dev)
  • slowapi rate-limiting middleware
  • All route routers
  • Global exception handler (no internal details in responses)
  • Request timing middleware
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.dependencies import limiter
from app.auth.router import router as auth_router
from app.monitoring.router import router as monitoring_router
from app.orders.router import router as orders_router
from app.sessions.router import router as sessions_router

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle hooks."""
    logger.info("VoiceOrder NLP Backend starting — env=%s", settings.ENVIRONMENT)
    yield
    logger.info("VoiceOrder NLP Backend shutting down")


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="VoiceOrder NLP Backend",
    description=(
        "Converts free-text restaurant orders to structured JSON.\n\n"
        "**Auth:** All routes except `/health` require `Authorization: Bearer <JWT>`.\n\n"
        "**Rate limits:** 20 req/min on `/order/parse`, 60 req/min on session messages, "
        "5 req/min on `/auth/token`."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Production: explicit origins only — never allow_origins=["*"]
# Development: localhost for local front-end / Swagger testing

if settings.is_production:
    _cors_origins = settings.allowed_origins_list
else:
    _cors_origins = ["http://localhost:3000", "http://localhost:5500", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,  # JWT in header — no cookies
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(orders_router, tags=["orders"])
app.include_router(sessions_router, tags=["sessions"])
app.include_router(monitoring_router, tags=["monitoring"])


# ── Middleware ────────────────────────────────────────────────────────────────


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Attach X-Process-Time (ms) to every response for client-side observability."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time"] = str(elapsed_ms)
    return response


# ── Global exception handler ──────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.
    Rule (Data Security spec): NEVER expose internals in API error responses.
    Full traceback goes to Railway structured logs only.
    """
    logger.error(
        "Unhandled exception | method=%s url=%s",
        request.method,
        request.url,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal error", "code": "INTERNAL_ERROR"},
    )
