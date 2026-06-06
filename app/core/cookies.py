"""Session-cookie helpers.

`set_session_cookie(response, token)` is called right after a
successful sign-in / sign-up. `clear_session_cookie(response)` is
called from /api/auth/logout. The cookie defaults come from env so
cross-site / same-site deploys can be flipped via config.

httpOnly + secure (in prod) + sameSite is non-negotiable — losing
httpOnly puts the JWT in reach of any XSS bug; losing secure leaks it
on http downgrade.
"""
import os
from typing import Literal

from fastapi import Response

from app.core.config import get_settings
from app.core.jwt import SESSION_TTL_SECONDS

SESSION_COOKIE_NAME = "tarrs_session"


def _samesite() -> Literal["lax", "none", "strict"]:
    raw = get_settings().COOKIE_SAMESITE.lower()
    if raw == "none":
        return "none"
    if raw == "strict":
        return "strict"
    return "lax"


def _secure() -> bool:
    """sameSite=none requires secure=true (browser requirement). Prod
    always secure regardless. Dev (NODE_ENV != production) leaves it
    off so localhost over plain http still works."""
    is_prod = os.environ.get("NODE_ENV", "development") == "production"
    return is_prod or _samesite() == "none"


def _domain() -> str | None:
    return get_settings().COOKIE_DOMAIN or None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_secure(),
        samesite=_samesite(),
        domain=_domain(),
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        domain=_domain(),
        httponly=True,
        secure=_secure(),
        samesite=_samesite(),
    )
