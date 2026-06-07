# FastAPI + Postgres API starter

A Tarrs-ready Python + FastAPI backend that talks to your own Postgres
via SQLAlchemy 2.0 (async) + Alembic. Same architectural discipline as
`express-postgres` (controller → service → model, response envelope,
structured errors, request observability, in-code authorization).

## Why FastAPI for AI / agent projects

Python is the lingua franca of the LLM SDK ecosystem — Anthropic,
OpenAI, LangChain, LangGraph, Letta, transformers, vLLM all live here
first. FastAPI's async-first design pairs cleanly with streaming
model outputs: every token decodes inside the same coroutine serving
the HTTP request. The `/api/chat` route + `app/agents/simple.py` ship
the **single-process agent pattern**: async generator → SSE frames →
`StreamingResponse`. No worker container, no IPC, no message broker.

Use this template (or `fastapi-supabase` if you want managed Supabase)
when you're building an AI / agent application. Use `express-postgres`
when you'd rather stay in the Node ecosystem.

## What's included

- FastAPI + Uvicorn (async, port 8080)
- **SQLAlchemy 2.0 async** + `asyncpg` driver + connection pool with
  statement / idle timeouts as session-level GUCs
- **Alembic** for migrations (hand-written DDL, NOT autogenerate)
- **Controller (router) → Service → Model** layering mirrors `express-postgres`
- **Response envelope**: every JSON endpoint returns
  `{success, message, data, code?}` via `app.core.response.Envelope[T]`
- **Structured errors**: `HTTPError(status_code, code, expected)`; the
  `expected=True` flag downgrades known upstream 5xx to WARN logs +
  forwards the message to the client
- **Request observability**: `structlog` + a middleware that tags
  every request with a short `request_id` via `contextvars` — every
  `get_logger().info(...)` inside the handler picks it up
  automatically; emits START / END / SLOW / ERROR lines
- `pydantic-settings`-validated config (fails at boot, not first request)
- **bcrypt + python-jose HS256 httpOnly cookie sessions** —
  email + password registration / login / logout, no Bearer dance
- **CSRF** middleware (Origin/Referer allowlist) on every mutation —
  cookie auth needs it
- Sample `/api/posts` resource: GET list + POST create + DELETE author-only
- **Streaming `/api/chat` SSE agent** (Anthropic) — the canonical
  agent pattern, hookable to any LLM SDK / LangChain / LangGraph
- OpenAPI docs at `/docs`

## Layout

```
app/
  main.py                # FastAPI app + middleware + handler wiring
  core/
    config.py            # Settings via pydantic-settings
    response.py          # Envelope[T] + ok()
    exceptions.py        # HTTPError + global handlers
    logging.py           # structlog + request_id middleware
    cookies.py           # set_session_cookie / clear_session_cookie
    jwt.py               # python-jose sign / verify
    password.py          # bcrypt hash / verify
  db/session.py          # async engine + AsyncSession + get_db dep
  models/                # SQLAlchemy DeclarativeBase models
  schemas/               # Pydantic v2 request / response
  services/              # business logic — only layer touching models
  deps/                  # get_db, get_current_user(_optional)
  middleware/csrf.py     # Origin/Referer allowlist
  routers/               # thin HTTP shell
  agents/simple.py       # streaming Anthropic example
migrations/              # Alembic migration files
alembic.ini
```

See `CLAUDE.md` for the architectural rules the AI scaffolding new
endpoints must follow.

## Auth model

Email + password, cookie-based sessions. Sign-in / sign-up are
proxied through this API (unlike the `fastapi-supabase` variant, which
delegates to Supabase Auth). Cookie is httpOnly + sameSite +
secure (in prod); jose-signed HS256, 7-day TTL.

`get_current_user` is the hard-gate FastAPI dep mounted on every
authenticated route. `get_current_user_optional` is the soft variant
that returns `None` for anonymous (used by `GET /api/auth/me`).

## How Tarrs uses this

Tarrs auto-injects:

- `DATABASE_URL` — points at the local Postgres sidecar (use
  `postgresql+asyncpg://...` so SQLAlchemy uses the async driver at
  runtime; Alembic strips the suffix to `psycopg2` internally for the
  sync migration run)
- `JWT_SECRET` — generated per-project, stored in Sandbox Secrets
- `ANTHROPIC_API_KEY` — optional, only for the `/api/chat` example

Sandbox runs `uvicorn` on port 8080 (Tarrs convention: frontend :3000,
Node backend :4000, Python/agent :8080). Public URL is
`<project-slug>.dev.tarrs.io`.

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# fill DATABASE_URL + JWT_SECRET (openssl rand -base64 48)
alembic upgrade head     # apply migrations/
uvicorn app.main:app --reload --port 8080
```

OpenAPI: http://localhost:8080/docs

## Schema changes

```bash
# 1. Edit / add a model under app/models/ + register in __init__.py
# 2. Generate an empty migration (NOT --autogenerate; hand-write the DDL)
alembic revision -m "add_something_cool"
# 3. Edit migrations/versions/<stamp>_add_something_cool.py
# 4. Apply
alembic upgrade head

# Roll back the latest:
alembic downgrade -1

# See applied / pending:
alembic current && alembic history
```

We deliberately do NOT call `Base.metadata.create_all()` at boot.
Migrations are the only source of truth for schema; `create_all`
would silently diverge.

## Adding a new resource — the recipe

See `CLAUDE.md`. Six steps: model → register → migration → schema →
service → router → wire.

## Streaming agent pattern

`/api/chat` shows the **single-process agent pattern** — async
generator producing SSE frames, wrapped in a `StreamingResponse`. No
separate worker container, no IPC. Replace `app/agents/simple.py`
with LangChain / LangGraph / your own logic; the route handler stays
the same.

For production at scale (long-running agents, distributed retries,
human-in-the-loop pauses), graduate to a queue + worker. Most "chat
with an LLM" use cases live happily on this pattern indefinitely.

## CORS + cookie recipe

Same-origin / shared eTLD+1: default `COOKIE_SAMESITE=lax` works.

Cross-origin (frontend on Vercel, backend on Tarrs sandbox):

```
COOKIE_SAMESITE=none
CORS_ORIGINS=https://your-frontend.vercel.app
CSRF_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

`sameSite=none` forces `secure=true` (browser requirement). Never
serve `none` over plain http.

## Endpoints (sample)

- `GET    /api/health`           — liveness (envelope)
- `POST   /api/auth/register`    — email + password, sets cookie
- `POST   /api/auth/login`       — email + password, sets cookie
- `GET    /api/auth/me`          — decoded session, null for anonymous
- `POST   /api/auth/logout`      — clears cookie
- `GET    /api/posts`            — list (auth-gated, envelope)
- `POST   /api/posts`            — create (auth-gated, envelope)
- `DELETE /api/posts/:id`        — delete (auth-gated, 404 if not yours)
- `POST   /api/chat`             — SSE stream from Anthropic (NOT envelope)
