"""FastAPI app entry point.

Boot order matters:
  1. Configure logging FIRST so import-time pydantic / uvicorn lines
     come out structured.
  2. Build the FastAPI app.
  3. Add CORS middleware (must run BEFORE CSRF + access-log so OPTIONS
     preflights are answered without going through any handler).
  4. Install exception handlers (envelope-shaping for HTTPError /
     starlette HTTPException / RequestValidationError / catch-all).
  5. Install CSRF middleware (cookie auth needs this).
  6. Install the access-log middleware LAST so the request_id is
     attached to every log line emitted by the handler chain.
  7. Wire routers under /api.
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import exceptions
from app.core import logging as core_logging
from app.core.config import get_settings
from app.middleware import csrf as csrf_middleware
from app.routers import auth, chat, health, posts

load_dotenv()
core_logging.configure_logging()

settings = get_settings()
app = FastAPI(
    title="My API",
    version="0.1.0",
    description="Coloom-ready FastAPI + Postgres backend (SQLAlchemy 2.0 async + Alembic).",
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )
elif os.environ.get("NODE_ENV", "development") != "production":
    # Dev convenience: with no allowlist, let localhost through so a
    # newly-cloned starter just works on `uvicorn`. Production with no
    # CORS_ORIGINS gets nothing — explicit by design.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )

exceptions.install(app)
csrf_middleware.install(app)
core_logging.install(app)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
