"""Single import point that materializes every model.

Importing this module is enough to register all subclasses on
`Base.metadata` — which is what Alembic's autogenerate diffs against
to detect schema changes. Add your new model here too.
"""
from app.models.base import Base
from app.models.post import Post
from app.models.user import User

__all__ = ["Base", "Post", "User"]
