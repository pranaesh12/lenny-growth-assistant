"""
Shared enumerations used across ORM models and API schemas.

All enums here inherit from both `str` and `Enum`. This dual
inheritance is required for two reasons:

    1. SQLAlchemy's `Enum` column type stores the member's `.value`
       (a plain string) in PostgreSQL as a native enum type or a
       constrained VARCHAR — `str, Enum` members serialize cleanly
       without custom type adapters.
    2. FastAPI / Pydantic v2 (used in the API layer, later phases)
       treats `str, Enum` members as JSON-serializable strings
       automatically, so the same enum class works identically as
       both a SQLAlchemy column type and a Pydantic/OpenAPI schema
       type with no duplication.

Each enum's member VALUES (not names) are what get persisted to the
database and exposed over the API — member names are Python-facing
only.
"""

from enum import Enum

__all__ = [
    "MessageRole",
    "ProviderType",
    "ArtifactType",
    "RenderFormat",
    "ChatMode",
]


class MessageRole(str, Enum):
    """
    Identifies who authored a given message within a conversation.

    Mirrors the standard chat-completion role convention used by
    LLM provider APIs (OpenAI, Anthropic, etc.), so message records
    can be passed through to a provider with minimal translation.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ProviderType(str, Enum):
    """
    Identifies which LLM provider handled or should handle a given
    request.

    Used to record provenance on generated content and to route
    requests to the correct provider integration (implemented in a
    later phase).
    """

    CLAUDE = "claude"
    OPENAI = "openai"
    OLLAMA = "ollama"


class ArtifactType(str, Enum):
    """
    Classifies the kind of content an `Artifact` record represents.

    Determines how the artifact's content should be rendered,
    validated, and displayed by the frontend.
    """

    ESSAY = "essay"
    MARKDOWN_DOC = "markdown_doc"
    HTML_SNIPPET = "html_snippet"
    NOTES = "notes"
    SUMMARY = "summary"


class RenderFormat(str, Enum):
    """
    Specifies the markup format an artifact or message's content
    should be rendered as on the client.
    """

    MARKDOWN = "markdown"
    HTML = "html"


class ChatMode(str, Enum):
    """
    Identifies the interaction mode a chat session is operating in,
    used to select prompt strategy and response behavior.
    """

    CHAT = "chat"
    ESSAY = "essay"
    QA = "qa"