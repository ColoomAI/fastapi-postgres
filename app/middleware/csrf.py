"""Origin/Referer-based CSRF defense.

Why this middleware: cookie sessions auto-attach to every request to
our domain, including ones initiated by an attacker page. Without a
gate, that page could trigger a state-changing POST as the
authenticated user. Origin/Referer matching kills that — browsers
attach Origin on every cross-origin write and the attacker can't
forge it.

Safe methods (GET / HEAD / OPTIONS) skip the check — they're not
supposed to mutate state, and exempting them keeps preflight + read
traffic unencumbered.

Set CSRF_ALLOWED_ORIGINS (comma-separated). If unset, falls back to
CORS_ORIGINS — 9/10 deploys want the same allowlist gating both.

Dev (NODE_ENV != production) with no allowlist is permissive so the
first-clone UX works. Production with no allowlist refuses every
mutation.
"""
import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.response import Envelope

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_from_referer(referer: str) -> str | None:
    """Strip path/query, return scheme://host[:port]. Returns None on
    malformed input rather than raising."""
    try:
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        return None


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def csrf_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        allowed = get_settings().csrf_origin_list
        if not allowed:
            if os.environ.get("NODE_ENV", "development") != "production":
                return await call_next(request)
            return JSONResponse(
                status_code=403,
                content=Envelope[None](
                    success=False,
                    message="CSRF: no allowed origins configured",
                    data=None,
                    code="ERR_CSRF",
                ).model_dump(exclude_none=False),
            )

        origin = request.headers.get("origin")
        if not origin:
            referer = request.headers.get("referer")
            origin = _origin_from_referer(referer) if referer else None
        if not origin or origin not in allowed:
            return JSONResponse(
                status_code=403,
                content=Envelope[None](
                    success=False,
                    message="CSRF: origin not allowed",
                    data=None,
                    code="ERR_CSRF",
                ).model_dump(exclude_none=False),
            )
        return await call_next(request)
