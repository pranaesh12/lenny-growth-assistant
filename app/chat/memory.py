"""
Conversation memory writer.

Persists the user message and assistant response via `MessageService`
(the write path goes through the service layer, unlike `context.py`'s
read path, per this phase's spec) — never touches SQLAlchemy directly.
"""

from app.models.enums import MessageRole, ProviderType
from app.models.message import Message
from app.chat.exceptions import ConversationSaveError
from app.services.message_service import MessageService
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["save_exchange"]


def save_exchange(
    session_id: str,
    user_content: str,
    assistant_content: str,
    provider_used: ProviderType,
    message_service: MessageService,
) -> tuple[Message, Message]:
    """
    Persists one chat exchange: the user's message followed by the
    assistant's response.

    Args:
        session_id: The session both messages belong to.
        user_content: The user's message text.
        assistant_content: The assistant's response text.
        provider_used: The LLM provider that generated the response.
        message_service: Service used to create both messages.

    Returns:
        A tuple of (user_message, assistant_message).

    Raises:
        ConversationSaveError: If either message fails to save.
    """
    try:
        user_message = message_service.create_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=user_content,
        )
        assistant_message = message_service.create_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            provider_used=provider_used,
        )
    except Exception as exc:
        raise ConversationSaveError(f"Failed to save conversation for session {session_id}: {exc}") from exc

    log.info("Conversation saved | session_id={}", session_id)
    return user_message, assistant_message