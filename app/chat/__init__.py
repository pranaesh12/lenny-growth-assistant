"""
Chat orchestration package.

Connects PostgreSQL session/message history, ChromaDB semantic
retrieval, and the LLM provider abstraction into a single
conversational pipeline via `ChatOrchestrator`.
"""

from app.chat.exceptions import (
    ChatOrchestrationError,
    ContextError,
    ConversationSaveError,
    HistoryError,
    PromptBuildError,
)
from app.chat.orchestrator import ChatOrchestrator
from app.chat.schemas import ChatRequest, ChatResponse

__all__ = [
    "ChatOrchestrator",
    "ChatRequest",
    "ChatResponse",
    "ChatOrchestrationError",
    "HistoryError",
    "ContextError",
    "PromptBuildError",
    "ConversationSaveError",
]