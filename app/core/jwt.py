"""Session JWT helpers via python-jose.

HS256 + an `exp` claim. Same shape and lifetime as the express-postgres
template's jose-based tokens — that's not an accident; pair the two
templates and a cookie minted by one is readable by the other (useful
for migrations).
"""
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from jose import JWTError, jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7d
SESSION_TTL_MS = SESSION_TTL_SECONDS * 1000


class SessionClaims(TypedDict, total=False):
    sub: str  # user id
    email: str
    exp: int  # unix seconds
    iat: int


def sign_session(user_id: str, email: str) -> str:
    """Mint a session token for a successful sign-in / sign-up. Caller
    is responsible for setting it as an httpOnly cookie."""
    now = datetime.now(UTC)
    payload: dict[str, str | int] = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, get_settings().JWT_SECRET, algorithm=ALGORITHM)


def verify_session(token: str) -> SessionClaims | None:
    """Decode + validate. Returns None on any failure (expired, bad
    signature, malformed) so callers can treat it as anonymous instead
    of branching on exception types."""
    try:
        decoded = jwt.decode(
            token,
            get_settings().JWT_SECRET,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        return None
    sub = decoded.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    return SessionClaims(
        sub=sub,
        email=decoded.get("email", "") if isinstance(decoded.get("email"), str) else "",
        exp=decoded.get("exp", 0) if isinstance(decoded.get("exp"), int) else 0,
        iat=decoded.get("iat", 0) if isinstance(decoded.get("iat"), int) else 0,
    )
