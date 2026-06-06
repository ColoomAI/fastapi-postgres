"""FastAPI deps for session loading + auth-required gating.

`get_current_user_optional` reads the cookie and returns the user (or
None) — use on routes that want optional auth (e.g. /me returns null
for anonymous instead of 401).

`get_current_user` is the hard gate — 401s if no cookie / forged /
expired. Mount on every authenticated route via Depends().
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import SESSION_COOKIE_NAME
from app.core.exceptions import HTTPError
from app.core.jwt import verify_session
from app.db.session import get_db
from app.models.user import User


@dataclass(frozen=True)
class CurrentUser:
    """Decoded user. `id` is a UUID — services take this directly so
    they don't have to re-parse the string form."""

    id: uuid.UUID
    email: str


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    claims = verify_session(token)
    if claims is None:
        return None
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        return None
    # The DB lookup confirms the user still exists (a recently-deleted
    # account with a still-valid JWT should NOT be treated as signed
    # in). Cheap because `users.id` is the PK.
    user = await db.get(User, user_id)
    if user is None:
        return None
    return CurrentUser(id=user.id, email=user.email)


async def get_current_user(
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> CurrentUser:
    if user is None:
        raise HTTPError(
            "Sign in required",
            status_code=401,
            code="ERR_AUTH_REQUIRED",
        )
    return user
