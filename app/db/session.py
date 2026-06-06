"""Async SQLAlchemy 2.0 engine + AsyncSession factory + `get_db` dep.

Single shared pool across the uvicorn process. Pool sizing of 10 is
generous for a single-container app talking to a sandbox-local
Postgres (sub-ms latency). If you point this at managed Postgres
(RDS / Neon) over the public internet, lower `pool_size` and consider
raising `pool_recycle`.

statement_timeout / idle_in_transaction_session_timeout guard against
slow queries wedging the pool — set as session-level GUCs via
`connect_args.server_settings` so they apply to every connection.
"""
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def _make_connect_args() -> dict[str, Any]:
    """asyncpg-specific connect args. server_settings = GUCs applied
    on every connection at acquire time."""
    args: dict[str, Any] = {
        "server_settings": {
            "statement_timeout": "30000",
            "idle_in_transaction_session_timeout": "60000",
        },
    }
    if get_settings().use_ssl:
        args["ssl"] = "require"
    return args


_settings = get_settings()

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=_make_connect_args(),
)

# expire_on_commit=False so service code can read attributes off a
# returned object AFTER the session is closed (FastAPI's dep-yield
# pattern closes on exit). Without this you'd get DetachedInstanceError
# on every read in the router.
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dep: yields an AsyncSession scoped to one request. The
    `async with` closes (and returns to the pool) automatically.

    Service functions take `AsyncSession` as their first arg — they
    DON'T import `SessionLocal` directly. Routers thread the session
    in via Depends(get_db)."""
    async with SessionLocal() as session:
        yield session
