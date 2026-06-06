from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class PostRead(BaseModel):
    """Outbound shape. `from_attributes=True` lets Pydantic build this
    directly from a SQLAlchemy model instance, so services can return
    rows without an extra dict-conversion step."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    author_id: str
    created_at: datetime
