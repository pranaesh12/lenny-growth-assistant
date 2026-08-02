"""
Artifact repository.

Provides database access for `Artifact` rows, on top of the common
CRUD operations from `BaseRepository`.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as ORMSession

from app.models.artifact import Artifact
from app.models.enums import ArtifactType, RenderFormat
from app.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository[Artifact]):
    """Repository for `Artifact` database access."""

    def __init__(self, db: ORMSession) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session.
        """
        super().__init__(db, Artifact)

    def create_artifact(
        self,
        session_id: str,
        title: str,
        type: ArtifactType,
        render_format: RenderFormat,
        content: str,
        kind: str | None = None,
        **extra_fields: Any,
    ) -> Artifact:
        """
        Creates and persists a new artifact.

        Args:
            session_id: The parent session this artifact belongs to.
            title: Human-readable artifact title.
            type: The kind of content this artifact represents.
            render_format: The markup format the content should be
                rendered as.
            content: The full artifact content.
            kind: Optional precise artifact template identifier
                (e.g. "prd"), distinct from the structural `type`.
            **extra_fields: Any additional column values to set.

        Returns:
            The newly created, persisted `Artifact`.
        """
        return self.create(
            session_id=session_id,
            title=title,
            type=type,
            render_format=render_format,
            content=content,
            kind=kind,
            **extra_fields,
        )
    def get_session_artifacts(self, session_id: str) -> list[Artifact]:
        """
        Fetches all artifacts belonging to a session.

        Args:
            session_id: The parent session's primary key.

        Returns:
            A list of `Artifact` rows ordered by `updated_at`
            descending (most recently edited first).
        """
        statement = (
            select(Artifact)
            .where(Artifact.session_id == session_id)
            .order_by(Artifact.updated_at.desc())
        )
        return list(self.db.execute(statement).scalars().all())