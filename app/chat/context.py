"""
Conversation history loader.

Loads a session's prior messages directly via `MessageRepository`
(per this phase's spec — the read path uses the repository layer
directly, while `memory.py`'s write path goes through the service
layer for its validation).
"""

from app.chat.exceptions import HistoryError
from app.models.message import Message
from app.repositories.message_repository import MessageRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["load_conversation_history"]


def load_conversation_history(
    session_id: str,
    message_repository: MessageRepository,
    max_messages: int,
) -> list[Message]:
    """
    Loads a session's conversation history, most recent N messages,
    in chronological order.

    Args:
        session_id: The session to load history for.
        message_repository: Repository used to fetch messages.
        max_messages: Maximum number of most-recent messages to return.

    Returns:
        A list of `Message` rows in chronological order (oldest
        first), truncated to at most `max_messages`.

    Raises:
        HistoryError: If history cannot be loaded.
    """
    try:
        history = message_repository.get_messages_for_session(session_id)
    except Exception as exc:
        raise HistoryError(f"Failed to load conversation history for session {session_id}: {exc}") from exc

    truncated = history[-max_messages:] if max_messages > 0 else []
    log.debug(
        "Loaded conversation history | session_id={} total={} truncated_to={}",
        session_id,
        len(history),
        len(truncated),
    )
    return truncated