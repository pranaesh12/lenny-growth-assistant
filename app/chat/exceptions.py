"""
Chat orchestration exceptions.

Each exception maps to a specific stage of the orchestration pipeline,
so failures are traceable to where they occurred:

    HistoryError            -> loading conversation history (context.py)
    ContextError             -> semantic retrieval of transcript chunks
    PromptBuildError         -> assembling the final prompt (prompt_builder.py)
    ConversationSaveError    -> persisting messages (memory.py)
    ChatOrchestrationError   -> base class; also used for LLM-call failures
                                 and any other top-level orchestration failure
"""


class ChatOrchestrationError(Exception):
    """Base class for all chat orchestration errors."""


class HistoryError(ChatOrchestrationError):
    """Raised when conversation history cannot be loaded."""


class ContextError(ChatOrchestrationError):
    """Raised when semantic retrieval of transcript chunks fails."""


class PromptBuildError(ChatOrchestrationError):
    """Raised when the final prompt cannot be assembled."""


class ConversationSaveError(ChatOrchestrationError):
    """Raised when the user or assistant message cannot be persisted."""


__all__ = [
    "ChatOrchestrationError",
    "HistoryError",
    "ContextError",
    "PromptBuildError",
    "ConversationSaveError",
]