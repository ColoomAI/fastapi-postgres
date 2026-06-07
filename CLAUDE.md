# Architecture (locked)

When you add or change code in this repo, **follow these rules**. They
are not preferences — they are how this template is supposed to work.
Deviating is a bug.

## When to pick this template

- You're building an **AI / LLM / agent app** (Anthropic / OpenAI /
  LangChain / LangGraph / Letta / transformers / vLLM). Python is the
  lingua franca of the LLM SDK ecosystem; FastAPI is its async-first
  API framework. The `/api/chat` route + `app/agents/simple.py` show
  the single-process streaming pattern you'll likely keep.
- You want a **typed Python API** with auto-generated OpenAPI docs at
  `/docs` for free.
- You want your own Postgres (not Supabase). If you want managed
  Supabase, see `fastapi-supabase`.

## Stack — pinned

| Concern | Choice | Don't substitute |
|---|---|---|
| Data access | **SQLAlchemy 2.0 async (`sqlalchemy[asyncio]`)** + `asyncpg` driver | No SQLModel (less mature for prod), no Tortoise / Peewee, no raw `psycopg` queries in routers. The ORM is SQLAlchemy 2.0 because that's what fastapi-supabase's idiomatic alternative is — one stack, two data layers. |
| Authorization | **In code, in `app/services/`** | Every protected operation checks `if resource.author_id != current_user.id: raise HTTPError("Not found", 404)` in the service. Routers parse and call; they never own the rule. |
| Auth (sessions) | bcrypt + python-jose HS256, httpOnly cookie | Don't ship JWT in Authorization header — cookies are what the matching `express-postgres` template uses. Don't replace python-jose; we picked it (vs PyJWT) for the wider FastAPI tutorial alignment. |
| Migrations | **Alembic** (`migrations/`), hand-written DDL | No `Base.metadata.create_all()`. Ever. Migrations are the only source of truth. Alembic's autogenerate is fine for first-pass diffing, but every commit's migration is hand-reviewed. |
| Validation | Pydantic v2 (`schemas/`) | No marshmallow / cattrs. EmailStr from `pydantic[email]` for email validation. |
| Response shape | `Envelope[T]` from `app.core.response` | Every JSON endpoint returns `Envelope[T]`. SSE / file-download endpoints are the only exception (see `routers/chat.py`). |
| Errors | `HTTPError(status_code, code, expected)` from `app.core.exceptions` | Don't raise FastAPI's `HTTPException` directly from service code — the global handler maps `HTTPError` into the envelope with `code` + `expected` semantics. |
| Streaming agents | **single-process: `StreamingResponse(async_generator)`** | Don't pull in Celery / Dramatiq / RQ unless you've outgrown the single-process pattern (long-running pauses, distributed retries, human-in-the-loop). |
| Logging | `structlog` via `app.core.logging.get_logger()` | Don't use stdlib `logging` directly; you'll lose `request_id` auto-binding. |
| Settings | `app.core.config.get_settings()` | Don't read `os.environ` ad-hoc — go through Settings so a missing var crashes the process at boot, not at the first request. |
| CSRF | `app.middleware.csrf` middleware mounted in `main.py` | Cookie auth needs CSRF. Origin/Referer allowlist already in place. Don't remove. |

## Folder layout — what each layer is for

```
app/
  main.py              FastAPI app + middleware order + handler install +
                       router wire. NO business logic.
  core/
    config.py          Settings via pydantic-settings (boot-time validate).
    response.py        Envelope[T] + ok() helper.
    exceptions.py      HTTPError + 4 global handlers (HTTPError,
                       StarletteHTTPException, RequestValidationError,
                       catch-all).
    logging.py         structlog + request_id middleware,
                       START / END / SLOW / ERROR access lines.
    cookies.py         set_session_cookie / clear_session_cookie.
                       Reads httpOnly + secure + sameSite from config.
    jwt.py             python-jose sign_session / verify_session (HS256).
    password.py        bcrypt hash / verify (cost 10).
  db/
    session.py         async engine + AsyncSession + get_db dep.
                       statement_timeout + idle_in_transaction_timeout
                       set as server-side GUCs on every connection.
  models/              SQLAlchemy 2.0 DeclarativeBase models, one per
                       table + __init__.py re-export. Every new model
                       MUST be registered in __init__.py so Alembic sees
                       it on Base.metadata.
  schemas/             Pydantic v2 request / response models. NO
                       business logic. NO imports from `services/` or
                       `routers/`.
  services/            Business logic. The ONLY layer that touches
                       models. Throws HTTPError on failure. Takes
                       AsyncSession + plain args. NO Request / Response
                       types here.
  deps/                FastAPI Depends() functions:
                       get_db (yields AsyncSession),
                       get_current_user (cookie -> user lookup, raises 401),
                       get_current_user_optional (same but returns None
                         for anonymous).
  middleware/
    csrf.py            Origin/Referer allowlist, mounted in main.py.
  routers/             Thin HTTP shells. Parse / Pydantic-validate, call
                       service, return ok(...). NO direct model access.
                       NO ownership checks (service owns those).
  agents/              Streaming-agent helpers (e.g. Anthropic SSE).
                       Replace `simple.py` with your own logic; the
                       single-process pattern stays the same.
migrations/            Alembic migration files. The schema source of
                       truth. Apply via `alembic upgrade head`.
alembic.ini            Alembic config (URL is read from env in env.py).
```

## The 6-file recipe — adding a new resource

1. `app/models/foo.py` — SQLAlchemy model. Add `Foo` to `app/models/__init__.py` so Alembic sees it.
2. `alembic revision -m "add_foo"` — generate empty migration; hand-write the DDL (don't trust `--autogenerate` blindly — review the diff).
3. `alembic upgrade head` — apply.
4. `app/schemas/foo.py` — Pydantic `Create` / `Read` models.
5. `app/services/foo.py` — `list_foos(db)`, `create_foo(db, ...)`, `delete_foo(db, foo_id, acting_user_id)`. All DB access + all ownership checks live here.
6. `app/routers/foo.py` — Depends(`get_db`), Depends(`get_current_user`), call service, return `ok(...)`. Wire in `app/main.py` with `app.include_router(...)`.

The router never touches a model. The service never reads a `Request`.

## Authorization in detail — ownership pattern

```python
# app/services/posts.py
async def delete_post(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    post = await db.get(Post, post_id)
    # 404 on both "doesn't exist" and "isn't yours" — no row-existence
    # leak. NEVER 403 here; "you can't have this post" implies it
    # exists somewhere.
    if post is None or post.author_id != acting_user_id:
        raise HTTPError("Not found", 404, code="ERR_NOT_FOUND")
    await db.delete(post)
    await db.commit()
```

The router thread `current_user.id` in via the dep. The check is HERE,
not in the router, because it's a property of the resource, not of
the HTTP transport.

## Streaming agent pattern

```python
# app/agents/simple.py
async def run_agent(prompt: str) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", ...) as res:
            async for line in res.aiter_lines():
                # process + yield SSE frames
                yield f"data: {json.dumps(event)}\n\n"
```

```python
# app/routers/chat.py
return StreamingResponse(
    run_agent(payload.prompt),
    media_type="text/event-stream",
)
```

**Replace `simple.py` with LangChain / LangGraph / your own logic.**
The shape stays: define an `async def run_agent(...) -> AsyncGenerator[str, None]`, yield SSE frames as work progresses. No worker container needed.

## Errors — `expected: True` semantics

When a 5xx is your fault → `raise HTTPError(msg, 500)`. Handler logs ERROR + stack, client sees `"Internal error"` (raw message may contain SQL fragments / internal IPs — never echo).

When a 5xx is a known upstream state → `raise HTTPError(msg, 502, expected=True)`. Handler logs WARN (no stack), client sees your message. Use this for:
- Anthropic / OpenAI / third-party API failures
- "Background job paused" or similar known states

## What NOT to do

- ❌ Don't add SQLModel / Tortoise / Peewee — use SQLAlchemy 2.0.
- ❌ Don't call a model from a router — go through `services/`.
- ❌ Don't validate request bodies in service code — that's the router's job.
- ❌ Don't check `if resource.author_id != user.id` in a router — that's the service's job.
- ❌ Don't `Base.metadata.create_all()`. Ever.
- ❌ Don't trust `alembic revision --autogenerate` blindly — review every diff.
- ❌ Don't add Celery / Dramatiq for "background tasks" the streaming pattern already covers.
- ❌ Don't `print()` or stdlib `logging.info(...)` — use `get_logger().info(...)`.
- ❌ Don't return raw dicts from routers — wrap in `ok(...)`.
- ❌ Don't read `os.environ` directly — go through `get_settings()`.
- ❌ Don't add Bearer-token auth on top of the cookie — pick one.
- ❌ Don't bypass `get_current_user` with a manual cookie decode in a router.

## What to do when in doubt

Read `app/routers/posts.py` + `app/services/posts.py` + `app/services/auth.py` — they're the canonical examples for the CRUD pattern. Read `app/agents/simple.py` + `app/routers/chat.py` for the streaming pattern.
