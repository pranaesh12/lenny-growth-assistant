"""
SQLAlchemy declarative base and reusable mixins.

This module is the common foundation every ORM model in the project
inherits from. It intentionally does NOT redefine the project's
`Base` — that single declarative base already lives in
`app.db.database` (Phase: Database Connection), and Alembic's
`env.py` (Phase 5) is wired to that exact module's `Base.metadata`
for autogenerate support.

Re-exporting it here (rather than creating a second, independent
`DeclarativeBase` subclass) ensures there is only ever one metadata
registry in the project. Two separate `Base` classes would silently
split model registration across two unrelated `MetaData` objects —
any model accidentally inheriting from the "wrong" one would be
invisible to Alembic's autogenerate diffing.

`app/models/base.py` is kept as the conventional import location for
models code (`from app.models.base import Base, TimestampMixin`),
while `app/db/database.py` remains the single owner of the Base
definition itself.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

# Single source of truth for the declarative base — see module
# docstring for why this is imported rather than redefined.
from app.db.database import Base

__all__ = ["Base", "TimestampMixin"]


class TimestampMixin:
    """
    Reusable mixin adding `created_at` and `updated_at` columns to
    any model that inherits from it, alongside `Base`.

    Both columns are timezone-aware (`DateTime(timezone=True)`),
    which is required for correct behavior against PostgreSQL's
    `timestamptz` type — Supabase (and PostgreSQL generally) stores
    all timestamps in UTC internally, and timezone-naive columns
    would silently lose offset information and invite subtle bugs
    when the app server and database run in different timezones.

    Both defaults are enforced at the DATABASE level via
    `server_default` / `server_onupdate` (PostgreSQL's `now()`)
    rather than in application code. This guarantees correct
    timestamps even for rows inserted or updated outside the ORM
    (e.g. via Supabase's SQL editor, a manual migration, or a direct
    `UPDATE` statement), and avoids clock-skew issues between the
    application server and the database server.

    Usage:
        class Session(Base, TimestampMixin):
            __tablename__ = "sessions"
            id: Mapped[int] = mapped_column(primary_key=True)
            # created_at / updated_at are inherited automatically
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="UTC timestamp of row creation, set once by the database.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc=(
            "UTC timestamp of the most recent row modification. "
            "Automatically refreshed by SQLAlchemy on every UPDATE "
            "issued through the ORM (via `onupdate`)."
        ),
    )