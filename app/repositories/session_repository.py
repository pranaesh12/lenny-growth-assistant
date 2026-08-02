"""
Session repository.

Provides database access for `Session` rows, on top of the common
CRUD operations from `BaseRepository`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session as ORMSession

from app.models.session import Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Repository for `Session` database access."""

    def __init__(self, db: ORMSession) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session.
        """
        super().__init__(db, Session)

    def get_session(self, session_id: str) -> Session | None:
        """
        Fetches a single session by its ID.

        Args:
            session_id: The session's primary key (e.g. "sess_...").

        Returns:
            The matching `Session`, or None if not found.
        """
        return self.get_by_id(session_id)

    def get_recent_sessions(
        self, limit: int = 20, include_archived: bool = False
    ) -> list[Session]:
        """
        Fetches the most recently updated sessions.

        Args:
            limit: Maximum number of sessions to return.
            include_archived: Whether to include archived sessions
                in the results. Defaults to False (active only).

        Returns:
            A list of `Session` rows ordered by `updated_at`
            descending (most recently updated first).
        """
        statement = select(Session).order_by(Session.updated_at.desc()).limit(limit)
        if not include_archived:
            statement = statement.where(Session.archived.is_(False))
        return list(self.db.execute(statement).scalars().all())

    def update_title(self, session_id: str, title: str) -> Session | None:
        """
        Updates a session's title.

        Args:
            session_id: The session's primary key.
            title: The new title to set.

        Returns:
            The updated `Session`, or None if not found.
        """
        return self.update(session_id, title=title)

    def archive_session(self, session_id: str) -> Session | None:
        """
        Marks a session as archived.

        Args:
            session_id: The session's primary key.

        Returns:
            The updated `Session`, or None if not found.
        """
        return self.update(session_id, archived=True)

    def restore_session(self, session_id: str) -> Session | None:
        """
        Restores a previously archived session (marks it active).

        Args:
            session_id: The session's primary key.

        Returns:
            The updated `Session`, or None if not found.
        """
        return self.update(session_id, archived=False)