"""
Message service.

Contains business logic for creating and querying messages within a
session. Uses `MessageRepository` for message data access and
`SessionRepository` to validate that a parent session exists before
creating a message — never touches SQLAlchemy models or query
constructs directly.
"""

from app.models.enums import MessageRole, ProviderType
from app.models.message import Message
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.services.exceptions import NotFoundError, ValidationError


class MessageService:
    """Business logic for message management."""

    def __init__(
        self,
        repository: MessageRepository,
        session_repository: SessionRepository,
    ) -> None:
        """
        Args:
            repository: Repository providing message data access.
            session_repository: Repository used to validate that a
                parent session exists before creating a message.
        """
        self.repository = repository
        self.session_repository = session_repository

    def create_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        content_type: str = "markdown",
        provider_used: ProviderType | None = None,
        artifact_id: str | None = None,
    ) -> Message:
        """
        Creates a new message within a session.

        Args:
            session_id: The parent session's primary key.
            role: Who authored the message.
            content: The full message text. Must not be blank.
            content_type: Render format of the content.
            provider_used: The LLM provider that generated the
                message, if it's an assistant response.
            artifact_id: Optional artifact this message references.

        Returns:
            The newly created `Message`.

        Raises:
            NotFoundError: If the parent session does not exist.
            ValidationError: If `content` is blank, `role` is not a
                valid `MessageRole`, or a user/system message is
                given a `provider_used` value (providers only ever
                generate assistant responses).
        """
        if self.session_repository.get_session(session_id) is None:
            raise NotFoundError(f"Cannot create a message: session '{session_id}' was not found.")

        if not content or not content.strip():
            raise ValidationError("Message content must not be blank.")

        if not isinstance(role, MessageRole):
            raise ValidationError(f"'{role}' is not a valid MessageRole.")

        if provider_used is not None and role != MessageRole.ASSISTANT:
            raise ValidationError(
                "provider_used may only be set on assistant messages."
            )

        return self.repository.create_message(
            session_id=session_id,
            role=role,
            content=content,
            content_type=content_type,
            provider_used=provider_used,
            artifact_id=artifact_id,
        )

    def get_message(self, message_id: str) -> Message:
        """
        Fetches a single message by ID.

        Args:
            message_id: The message's primary key.

        Returns:
            The matching `Message`.

        Raises:
            NotFoundError: If no message exists with that ID.
        """
        message = self.repository.get_by_id(message_id)
        if message is None:
            raise NotFoundError(f"Message '{message_id}' was not found.")
        return message

    def list_messages(self, session_id: str) -> list[Message]:
        """
        Lists all messages for a session in chronological order.

        Args:
            session_id: The parent session's primary key.

        Returns:
            A list of `Message` rows, oldest first.

        Raises:
            NotFoundError: If the session does not exist.
        """
        if self.session_repository.get_session(session_id) is None:
            raise NotFoundError(f"Session '{session_id}' was not found.")
        return self.repository.get_messages_for_session(session_id)

    def get_session_history(self, session_id: str) -> list[Message]:
        """
        Fetches the full conversation history for a session, suitable
        for passing to an LLM provider as prior context.

        Args:
            session_id: The parent session's primary key.

        Returns:
            A list of `Message` rows in chronological order.

        Raises:
            NotFoundError: If the session does not exist.
        """
        # Currently identical to list_messages(); kept as a distinct
        # method since its purpose (building LLM context) is
        # semantically different and may diverge later (e.g. applying
        # a context-window truncation policy).
        return self.list_messages(session_id)

    def delete_message(self, message_id: str) -> None:
        """
        Permanently deletes a single message.

        Args:
            message_id: The message's primary key.

        Raises:
            NotFoundError: If no message exists with that ID.
        """
        self.get_message(message_id)
        self.repository.delete(message_id)