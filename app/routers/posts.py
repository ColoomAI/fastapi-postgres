import uuid

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HTTPError
from app.core.response import Envelope, ok
from app.db.session import get_db
from app.deps.auth import CurrentUser, get_current_user
from app.schemas.post import PostCreate, PostRead
from app.services import posts as posts_service

router = APIRouter()


def _to_read(row: object) -> PostRead:
    # PostRead has from_attributes=True, but `id` and `author_id` are
    # uuid.UUID on the model and PostRead declares them as str — the
    # str() cast happens explicitly here so the schema stays simple.
    return PostRead.model_validate(
        {
            "id": str(getattr(row, "id")),  # noqa: B009
            "title": getattr(row, "title"),  # noqa: B009
            "body": getattr(row, "body"),  # noqa: B009
            "author_id": str(getattr(row, "author_id")),  # noqa: B009
            "created_at": getattr(row, "created_at"),  # noqa: B009
        },
    )


@router.get("/posts", response_model=Envelope[list[PostRead]])
async def list_posts(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> Envelope[list[PostRead]]:
    rows = await posts_service.list_posts(db)
    return ok([_to_read(r) for r in rows])


@router.post("/posts", response_model=Envelope[PostRead], status_code=201)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[PostRead]:
    row = await posts_service.create_post(
        db,
        title=payload.title,
        body=payload.body,
        author_id=user.id,
    )
    return ok(_to_read(row), message="Post created")


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str = Path(min_length=36, max_length=36),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError as exc:
        raise HTTPError("Invalid id", 400) from exc
    await posts_service.delete_post(
        db,
        post_id=post_uuid,
        acting_user_id=user.id,
    )
