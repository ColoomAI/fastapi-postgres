"""Auth router — register, login, me, logout.

Cookie-based sessions: a successful register / login sets a 7-day
httpOnly cookie; subsequent requests carry it automatically; logout
clears it.

Email + password is intentionally the only credential flow. If you
need magic-link / OAuth / Google, swap to the supabase variant
(fastapi-supabase) or layer a provider on top here.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_session_cookie, set_session_cookie
from app.core.jwt import sign_session
from app.core.response import Envelope, ok
from app.db.session import get_db
from app.deps.auth import CurrentUser, get_current_user_optional
from app.schemas.auth import Credentials, UserPublic
from app.services.auth import login_user, register_user

router = APIRouter()


@router.post(
    "/auth/register",
    response_model=Envelope[UserPublic],
    status_code=201,
)
async def register(
    payload: Credentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[UserPublic]:
    user = await register_user(db, payload.email, payload.password)
    token = sign_session(str(user.id), user.email)
    set_session_cookie(response, token)
    return ok(UserPublic(id=str(user.id), email=user.email), message="Registered")


@router.post("/auth/login", response_model=Envelope[UserPublic])
async def login(
    payload: Credentials,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Envelope[UserPublic]:
    user = await login_user(db, payload.email, payload.password)
    token = sign_session(str(user.id), user.email)
    set_session_cookie(response, token)
    return ok(UserPublic(id=str(user.id), email=user.email), message="Signed in")


@router.get("/auth/me", response_model=Envelope[UserPublic | None])
async def me(
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> Envelope[UserPublic | None]:
    """Returns the current user, or null when anonymous. NOT a 401 on
    no-cookie — the frontend decides what to render for anonymous."""
    if user is None:
        return ok(None)
    return ok(UserPublic(id=str(user.id), email=user.email))


@router.post("/auth/logout", status_code=204)
async def logout(response: Response) -> None:
    clear_session_cookie(response)
