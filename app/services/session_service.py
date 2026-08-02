"""
Session service.

Contains business logic for creating, querying, and managing
sessions. Uses only `SessionRepository` for data access — never
touches SQLAlchemy models or query constructs directly.
"""

from app.models.session import Session
from app.repositories.session_repository import SessionRepository
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


class SessionService:
    """Business logic for session management."""

    def __init__(self, repository: SessionRepository) -> None:
        """
        Args:
            repository: Repository providing session data access.
        """
        self.repository = repository

    def create_session(self, title: str | None = None) -> Session:
        """
        Creates a new session.

        Args:
            title: Optional initial title. If omitted or blank, the
                model's default ("New Session") is used.

        Returns:
            The newly created `Session`.

        Raises:
            ValidationError: If a title is provided but exceeds the
                model's maximum length.
        """
        if title is not None:
            title = title.strip()
            if len(title) > 200:
                raise ValidationError("Session title must not exceed 200 characters.")
            if not title:
                # Treat a blank/whitespace-only title as "no title given"
                # rather than persisting an empty string.
                title = None

        if title:
            return self.repository.create(title=title)
        return self.repository.create()

    def get_session(self, session_id: str) -> Session:
        """
        Fetches a session by ID.

        Args:
            session_id: The session's primary key.

        Returns:
            The matching `Session`.

        Raises:
            NotFoundError: If no session exists with that ID.
        """
        session = self.repository.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session '{session_id}' was not found.")
        return session

    def list_sessions(self, limit: int = 20, include_archived: bool = False) -> list[Session]:
        """
        Lists the most recently updated sessions.

        Args:
            limit: Maximum number of sessions to return.
            include_archived: Whether to include archived sessions.

        Returns:
            A list of `Session` rows, most recently updated first.

        Raises:
            ValidationError: If `limit` is not a positive integer.
        """
        if limit <= 0:
            raise ValidationError("limit must be a positive integer.")
        return self.repository.get_recent_sessions(limit=limit, include_archived=include_archived)

    def rename_session(self, session_id: str, new_title: str) -> Session:
        """
        Renames a session.

        Args:
            session_id: The session's primary key.
            new_title: The new title to set.

        Returns:
            The updated `Session`.

        Raises:
            NotFoundError: If no session exists with that ID.
            ConflictError: If the session is archived (archived
                sessions are read-only and cannot be renamed).
            ValidationError: If `new_title` is blank or exceeds the
                model's maximum length.
        """
        session = self.get_session(session_id)

        if session.archived:
            raise ConflictError(
                f"Session '{session_id}' is archived and cannot be renamed. "
                "Restore it first."
            )

        new_title = new_title.strip()
        if not new_title:
            raise ValidationError("Session title must not be blank.")
        if len(new_title) > 200:
            raise ValidationError("Session title must not exceed 200 characters.")

        updated = self.repository.update_title(session_id, new_title)
        assert updated is not None  # existence already confirmed above
        return updated

    def archive_session(self, session_id: str) -> Session:
        """
        Archives a session.

        Args:
            session_id: The session's primary key.

        Returns:
            The updated `Session`.

        Raises:
            NotFoundError: If no session exists with that ID.
            ConflictError: If the session is already archived.
        """
        session = self.get_session(session_id)

        if session.archived:
            raise ConflictError(f"Session '{session_id}' is already archived.")

        updated = self.repository.archive_session(session_id)
        assert updated is not None
        return updated

    def delete_session(self, session_id: str) -> None:
        """
        Permanently deletes a session and all of its messages and
        artifacts (via cascade).

        Args:
            session_id: The session's primary key.

        Raises:
            NotFoundError: If no session exists with that ID.
        """
        # Confirms existence and raises NotFoundError if missing,
        # so a delete of a nonexistent session fails clearly rather
        # than silently no-op'ing.
        self.get_session(session_id)
        self.repository.delete(session_id)