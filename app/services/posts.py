"""Posts business logic.

The ownership check ("only the author can delete their own post")
lives here, NOT in the router. It's a property of the resource, not
of the HTTP transport. If you later swap REST for GraphQL or wire a
Server Action, the check moves with the service unchanged.
"""
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HTTPError
from app.models.post import Post

LIST_LIMIT = 100


async def list_posts(db: AsyncSession) -> list[Post]:
    result = await db.execute(
        select(Post).order_by(desc(Post.created_at)).limit(LIST_LIMIT),
    )
    return list(result.scalars().all())


async def create_post(
    db: AsyncSession,
    *,
    title: str,
    body: str,
    author_id: uuid.UUID,
) -> Post:
    post = Post(title=title, body=body, author_id=author_id)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    """Delete a post. Returns 404 for both "doesn't exist" and "exists
    but belongs to someone else" so non-owners can't probe for row
    existence."""
    post = await db.get(Post, post_id)
    if post is None or post.author_id != acting_user_id:
        raise HTTPError("Not found", 404, code="ERR_NOT_FOUND")
    await db.delete(post)
    await db.commit()
