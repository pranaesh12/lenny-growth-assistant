"""
Configuration repository.

Provides database access for the application's global `Configuration`
row, on top of the common CRUD operations from `BaseRepository`. The
application maintains a single active configuration; enforcing that
invariant (e.g. ensuring exactly one row exists) is a service-layer
concern — this repository only reads and writes whatever rows exist.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as ORMSession

from app.models.configuration import Configuration
from app.repositories.base import BaseRepository


class ConfigurationRepository(BaseRepository[Configuration]):
    """Repository for `Configuration` database access."""

    def __init__(self, db: ORMSession) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session.
        """
        super().__init__(db, Configuration)

    def get_configuration(self) -> Configuration | None:
        """
        Fetches the application's active configuration row.

        The application is expected to maintain a single
        `Configuration` row; if more than one exists, the most
        recently updated row is returned. Returns None if no
        configuration row exists yet.

        Returns:
            The active `Configuration`, or None if none exists.
        """
        statement = select(Configuration).order_by(Configuration.updated_at.desc()).limit(1)
        return self.db.execute(statement).scalar_one_or_none()

    def update_configuration(self, config_id: str, **fields: Any) -> Configuration | None:
        """
        Updates the configuration row's fields.

        Args:
            config_id: The primary key of the configuration row to
                update.
            **fields: Column values to set (e.g. `active_provider`,
                `default_model`, `temperature`, `rag_enabled`).

        Returns:
            The updated `Configuration`, or None if no row exists
            with that primary key.
        """
        return self.update(config_id, **fields)