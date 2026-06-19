# VoiceOrder NLP Backend

A FastAPI service that converts free-text restaurant orders into structured JSON using a 6-step spaCy NLP pipeline. Built for multi-turn voice-order conversations with JWT auth, Redis session state, and PostgreSQL persistence.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI 0.111 + Uvicorn |
| Auth | JWT RS256 (python-jose) + bcrypt (passlib) |
| NLP | spaCy 3.7 (`en_core_web_sm`) + rapidfuzz + word2number |
| Database | PostgreSQL 15 (asyncpg + SQLAlchemy 2 async) |
| Cache / Sessions | Redis 7 (redis-py asyncio) |
| Migrations | Alembic 1.13 (async engine) |
| Rate Limiting | slowapi (per-user JWT key or IP fallback) |
| Validation | Pydantic v2 + pydantic-settings |
| Testing | pytest-asyncio + httpx ASGI client |
| Lint | ruff |
| Deployment | Docker → Railway |

---

## Project Structure

```
voiceorder/
├── .env.example                    # env template — copy to .env
├── .gitignore
├── alembic.ini                     # points to db/migrations; URL injected at runtime
├── docker-compose.yml              # local dev: api + postgres + redis
├── Dockerfile                      # python:3.11-slim, non-root user, spaCy baked in
├── pytest.ini                      # asyncio_mode=auto, testpaths=tests, cov≥80%
├── requirements.txt                # pinned deps
├── .github/
│   └── workflows/
│       └── ci.yml                  # lint → test → (Railway auto-deploy on main)
├── app/
│   ├── main.py                     # FastAPI app, CORS, rate-limit middleware, routers
│   ├── config.py                   # pydantic-settings Settings singleton
│   ├── dependencies.py             # get_db, get_redis, get_current_user, limiter
│   ├── auth/
│   │   ├── models.py               # User ORM (id UUID PK, email, hashed_pw, is_active)
│   │   ├── schemas.py              # RegisterRequest, TokenRequest, UserResponse, TokenResponse
│   │   ├── service.py              # hash_password, verify_password, create_access_token
│   │   └── router.py               # POST /auth/register  POST /auth/token
│   ├── monitoring/
│   │   └── router.py               # GET /health  GET /metrics
│   ├── nlp/
│   │   ├── entity_ruler.py         # spaCy EntityRuler builder + DEFAULT_MENU_ITEMS (50 items)
│   │   ├── pipeline.py             # extract_entities() — 6-step pipeline
│   │   └── schemas.py              # ParsedOrder, OrderItem, RawEntity
│   ├── orders/
│   │   ├── models.py               # MenuItem, Order ORM (items JSONB, for_review, confidence)
│   │   ├── schemas.py              # ParseRequest, OrderResponse, HistoryResponse
│   │   ├── service.py              # _compute_total, persist_order, get_history
│   │   └── router.py               # POST /order/parse  GET /orders/history
│   └── sessions/
│       ├── models.py               # Session ORM (user_id FK, status, turn_count, expires_at)
│       ├── schemas.py              # SessionStartResponse, MessageRequest, MessageResponse
│       ├── service.py              # create_session, process_message, close_session (Redis)
│       └── router.py               # POST /session/start  POST /session/{id}/message
│                                   # GET  /session/{id}/order  DELETE /session/{id}
├── db/
│   ├── base.py                     # SQLAlchemy DeclarativeBase
│   └── migrations/
│       ├── env.py                  # async Alembic env; reads DATABASE_URL from env
│       ├── script.py.mako
│       └── versions/
│           └── 001_initial_schema.py  # users → menu_items → sessions → orders
├── scripts/
│   └── generate_keys.sh            # openssl RSA 2048 keygen; prints .env instructions
└── tests/
    ├── conftest.py                 # fixtures: db_session (rollback), _FakeRedis, client, users
    ├── test_auth.py                # register, token, JWT lifecycle, protected routes
    ├── test_nlp.py                 # pipeline unit tests + p95 latency gate + accuracy ≥90%
    ├── test_orders.py              # /order/parse integration, history pagination, metrics
    └── test_sessions.py            # multi-turn session flow, user isolation, close → persist
```

---

## API Endpoints

### Auth — `/auth` (rate: 5 req/min, IP-keyed)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | ❌ | Create account. Returns 201 with user object. |
| POST | `/auth/token` | ❌ | Login. Returns RS256 JWT valid for 24h (dev) / 1h (prod). |

**Register body:** `{ "email": "string", "password": "string (8–72 chars)" }`  
**Token body:** `{ "email": "string", "password": "string" }`  
**Token response:** `{ "access_token": "...", "token_type": "bearer" }`

### Orders — `/order` (rate: 20 req/min, user-keyed)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/order/parse` | ✅ Bearer | Parse free-text → structured order. Persists to DB. |
| GET | `/orders/history` | ✅ Bearer | Paginated order history for authenticated user. |

**Parse body:** `{ "text": "I want 2 large pepperoni pizzas with extra cheese" }`  
**Parse response:**
```json
{
  "id": "uuid",
  "items": [{"name": "pepperoni pizza", "quantity": 2, "size": "large", "modifiers": ["extra cheese"], "unit_price": 12.99}],
  "total_price": 25.98,
  "confidence": 0.87,
  "for_review": false,
  "raw_entities": [{"text": "pepperoni pizza", "label": "FOOD", "start": 12, "end": 27}],
  "processing_time_ms": 42.3
}
```

### Sessions — `/session` (rate: 60 req/min on messages)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/session/start` | ✅ Bearer | Create multi-turn session. Returns session_id + expiry. |
| POST | `/session/{id}/message` | ✅ Bearer | Send utterance; NLP merged with existing order. |
| GET | `/session/{id}/order` | ✅ Bearer | Read current accumulated order from Redis. |
| DELETE | `/session/{id}` | ✅ Bearer | Close session; persist final order to DB. |

**Message body:** `{ "text": "string (1–500 chars)" }`  
**Message response:** `{ "updated_order": {...}, "turn": 3, "context_applied": true }`

> `context_applied: true` means "make that 3" / "add extra cheese" style contextual update occurred.

### Monitoring — no auth required

| Method | Path | Rate | Description |
|---|---|---|---|
| GET | `/health` | Unlimited | DB + Redis connectivity check. Always HTTP 200; inspect `status` field. |
| GET | `/metrics` | 10/min | Aggregated counters from Redis: orders_today, error_rate, avg_latency_ms. |

---

## NLP Pipeline (6 Steps)

```
Input text
  │
  ▼
Step 1 — Preprocess
  Strip control chars (\x00–\x1F, \x7F)
  Hard truncate at 500 chars
  Lowercase + normalize whitespace

  ▼
Step 2 — Number normalization
  word2number: "two large" → "2 large"

  ▼
Step 3 — spaCy EntityRuler (BEFORE NER)
  FOOD:     exact + token-level match from 50-item menu
  SIZE:     small | medium | large | xl | mini | regular
  MODIFIER: extra | no | without | add | light | double | …

  ▼
Step 4 — spaCy NER
  CARDINAL: quantity integers (spaCy built-in)
  Discards: GPE, ORG, PERSON, LOC, DATE, TIME, MONEY, PERCENT

  ▼
Step 5 — Entity Assembly
  qty   ← nearest CARDINAL within 3 tokens of FOOD
  size  ← SIZE entity within 4 tokens of FOOD
  mods  ← MODIFIER + following token

  ▼
Step 6 — Menu Matching (rapidfuzz)
  fuzz.token_sort_ratio, score_cutoff=75
  Miss → for_review=true + nearest suggestion

  ▼
Step 7 — Confidence
  confidence = (matched_entities / total_entities) × avg(fuzzy_scores)
  < 0.6 → for_review = true
  Target: p95 latency < 300 ms
```

---

## Database Schema

```sql
users       (id UUID PK, email VARCHAR UNIQUE, hashed_pw, created_at, is_active BOOL)
menu_items  (id UUID PK, name, category, price NUMERIC, modifiers JSONB, tags JSONB, created_at)
sessions    (id UUID PK, user_id FK→users, status VARCHAR(20), turn_count INT,
             created_at, expires_at DEFAULT now()+30min)
orders      (id UUID PK, session_id FK→sessions nullable, user_id FK→users,
             items JSONB, total_price NUMERIC, status VARCHAR(20),
             confidence FLOAT, for_review BOOL, created_at, updated_at)

Indexes: idx_users_email (unique), idx_orders_user, idx_orders_session,
         idx_sessions_user, idx_sessions_status, idx_menu_items_name
```

---

## Redis Schema

| Key | Type | TTL | Content |
|---|---|---|---|
| `session:{uuid}` | JSON string | 1800s (reset on each message) | `{session_id, user_id, turn, current_order, last_food_entity, conversation[]}` |
| `metrics:orders_today` | INCR counter | none | Total `/order/parse` calls today |
| `metrics:errors_today` | INCR counter | none | Total 5xx responses today |
| `metrics:latency_sum` | INCRBY counter | none | Sum of processing_time_ms |
| `metrics:latency_count` | INCR counter | none | Parse call count (denominator) |
| `metrics:for_review_today` | INCR counter | none | Parses flagged for review |

Session TTL is **reset on every message** — idle timeout semantics.  
Session ownership is validated against JWT `sub` on every Redis read/write — no cross-user access.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://user:pw@host:5432/db` |
| `REDIS_URL` | ✅ | — | `redis://user:pw@host:6379` |
| `JWT_PRIVATE_KEY` | ✅ | — | Full PEM string for RS256 signing |
| `JWT_PUBLIC_KEY` | ✅ | — | Full PEM string for RS256 verification |
| `ENVIRONMENT` | ✅ | `development` | `development` \| `production` \| `test` |
| `ACCESS_TOKEN_EXPIRE_HOURS` | ❌ | `24` | JWT TTL in hours |
| `ALLOWED_ORIGINS` | ❌ | `http://localhost:3000,...` | Comma-separated CORS origins |
| `SPACY_MODEL` | ❌ | `en_core_web_sm` | spaCy model name |
| `NLP_CONFIDENCE_THRESHOLD` | ❌ | `0.6` | Below this → `for_review=true` |
| `FUZZY_SCORE_CUTOFF` | ❌ | `75` | rapidfuzz score_cutoff (0–100) |

---

## Quick Start (Docker)

```bash
# 1. Copy env template
cp .env.example .env

# 2. Generate RS256 keys and paste into .env
bash scripts/generate_keys.sh

# 3. Start all services (api + postgres + redis)
docker compose up --build

# 4. Run migrations (separate terminal)
docker compose exec api alembic upgrade head

# 5. Verify
curl http://localhost:8000/health
# → {"status":"ok","checks":{"db":true,"redis":true},...}
```

Swagger UI: http://localhost:8000/docs  
ReDoc: http://localhost:8000/redoc

---

## Running Tests

Tests use an in-memory `_FakeRedis` (no external Redis needed) and a real test PostgreSQL database. All transactions are rolled back after each test.

```bash
# Requires: PostgreSQL at localhost:5432 with DB voiceorder_test (user: test, pw: test)
# Keys are auto-generated per test session — no .env needed for tests

pytest tests/ -v
# Coverage threshold: 80% (fails below)

# Single module
pytest tests/test_nlp.py -v
pytest tests/test_auth.py -v
pytest tests/test_orders.py -v
pytest tests/test_sessions.py -v
```

CI runs the full suite on every push (GitHub Actions: `.github/workflows/ci.yml`).

---

## Deployment (Railway)

Railway auto-deploys on push to `main` via GitHub integration.

1. Create a Railway project; connect your GitHub repo.
2. Add PostgreSQL plugin and Redis plugin from Railway dashboard.
3. Set environment variables in Railway → Variables:
   - `DATABASE_URL` (auto-set by Railway PostgreSQL plugin as `${{Postgres.DATABASE_URL}}`)
   - `REDIS_URL` (auto-set by Railway Redis plugin)
   - `JWT_PRIVATE_KEY` — paste full PEM (multi-line accepted)
   - `JWT_PUBLIC_KEY` — paste full PEM
   - `ENVIRONMENT=production`
   - `ACCESS_TOKEN_EXPIRE_HOURS=1`
   - `ALLOWED_ORIGINS=https://your-frontend.vercel.app`
4. Set start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Railway runs the Dockerfile automatically. Health check: `GET /health`.

---

## Key Design Decisions

**RS256 over HS256** — asymmetric JWT means the public key can be distributed to verify tokens without exposing the signing secret. Required for any microservice architecture.

**Redis for session state** — PostgreSQL stores session metadata and final orders; Redis holds live conversation context (turn history, accumulated order). 30-minute TTL reset on each message provides idle-timeout semantics without a cron job.

**EntityRuler before NER** — spaCy's EntityRuler runs before the statistical NER so menu vocabulary takes priority over spaCy's default classifications. `overwrite_ents=True` ensures custom FOOD labels win.

**FakeRedis in tests** — avoids a Redis instance for unit/integration tests. All 5 methods used by the app (`get`, `set`, `delete`, `incr`, `incrby`) are implemented as an in-memory dict.

**`for_review` flag** — orders with confidence < 0.6 or any fuzzy-match miss are flagged. This surfaces ambiguous orders to staff without blocking the API response.

**No internal details in error responses** — all unhandled exceptions log full tracebacks to structured logs but return `{"detail": "Internal error", "code": "INTERNAL_ERROR"}` to clients.
