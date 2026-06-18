# ─────────────────────────────────────────────────────────────────────────────
# VoiceOrder NLP Backend — Dockerfile
# Target: Railway container (512 MB RAM free tier)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# Prevent .pyc files and enable unbuffered stdout (Railway log streaming)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── spaCy model (baked into image; ~40 MB) ───────────────────────────────────
RUN python -m spacy download en_core_web_sm

# ── App source ────────────────────────────────────────────────────────────────
COPY . .

# ── Non-root user (security best practice) ───────────────────────────────────
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "asyncio"]
