"""Auth business logic.

Routers in `app/routers/auth.py` are thin shells that parse input and
call into here; everything that touches the DB / hashes a password
lives in this file. Session minting happens at the router level (which
owns the Response) right after a successful call.

Email-collision response is deliberately generic ("Sign-in failed")
to avoid an account-enumeration oracle. Trade off if you want a
friendlier UX.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HTTPError
from app.core.password import hash_password, verify_password
from app.models.user import User

# Indistinguishable-by-timing trick: bcrypt.checkpw runs against a
# fixed dummy hash even when the user doesn't exist so missing-user
# and wrong-password both take ~80ms. Don't randomize per request —
# that would re-introduce the timing leak.
_DUMMY_HASH = "$2b$10$abcdefghijklmnopqrstuvCqJYdv0fH.iWAY5g8mN4KX5yhEJ4hbxe"


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Create a user. Raises HTTPError(400, ERR_AUTH_FAILED) on email
    collision (intentionally vague — see module docstring)."""
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPError(
            "Sign-in failed",
            status_code=400,
            code="ERR_AUTH_FAILED",
        ) from exc
    await db.refresh(user)
    return user


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Verify credentials. Raises HTTPError(401, ERR_AUTH_FAILED) on
    any failure — never "no such user" or "wrong password" separately
    (avoids an enumeration oracle)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    ok = (
        verify_password(password, user.password_hash)
        if user is not None
        else verify_password(password, _DUMMY_HASH)
    )
    if user is None or not ok:
        raise HTTPError(
            "Sign-in failed",
            status_code=401,
            code="ERR_AUTH_FAILED",
        )
    return user
