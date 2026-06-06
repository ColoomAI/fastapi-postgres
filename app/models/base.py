"""SQLAlchemy 2.0 declarative base. One Base for the whole app — every
model inherits from this so Alembic's autogenerate sees them all when
it diffs `Base.metadata` against the live schema."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
