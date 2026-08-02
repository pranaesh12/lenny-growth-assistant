"""
Message repository.

Provides database access for `Message` rows, on top of the common
CRUD operations from `BaseRepository`.
"""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as ORMSession

from app.models.enums import MessageRole, ProviderType
from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for `Message` database access."""

    def __init__(self, db: ORMSession) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session.
        """
        super().__init__(db, Message)

    def create_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        content_type: str = "markdown",
        provider_used: ProviderType | None = None,
        artifact_id: str | None = None,
        **extra_fields: Any,
    ) -> Message:
        """
        Creates and persists a new message.

        Args:
            session_id: The parent session this message belongs to.
            role: Who authored the message (user, assistant, system).
            content: The full message text.
            content_type: Render format of `content`. Defaults to
                "markdown".
            provider_used: The LLM provider that generated this
                message, if applicable.
            artifact_id: Optional artifact this message produced or
                references.
            **extra_fields: Any additional column values to set.

        Returns:
            The newly created, persisted `Message`.
        """
        return self.create(
            session_id=session_id,
            role=role,
            content=content,
            content_type=content_type,
            provider_used=provider_used,
            artifact_id=artifact_id,
            **extra_fields,
        )

    def get_messages_for_session(self, session_id: str) -> list[Message]:
        """
        Fetches all messages belonging to a session, in chronological
        order.

        Args:
            session_id: The parent session's primary key.

        Returns:
            A list of `Message` rows ordered by `created_at`
            ascending (oldest first), matching conversation order.
        """
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def delete_messages_for_session(self, session_id: str) -> int:
        """
        Deletes all messages belonging to a session.

        Note: under normal operation this is handled automatically by
        the `Session.messages` cascade when a session itself is
        deleted. This method exists for the standalone case of
        clearing a session's messages without deleting the session.

        Args:
            session_id: The parent session's primary key.

        Returns:
            The number of message rows deleted.
        """
        statement = delete(Message).where(Message.session_id == session_id)
        result = self.db.execute(statement)
        self.db.commit()
        return result.rowcount