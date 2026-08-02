"""
Typed request/response models for chat orchestration.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import LLMProvider

__all__ = ["ChatRequest", "Citation", "RetrievedChunkSchema", "TokenUsage", "ChatResponse"]


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": None,
                "message": "How do I find product market fit?",
            }
        }
    )

    session_id: str | None = Field(
        default=None,
        description="Existing session to continue. Omit to start a new session.",
    )
    message: str = Field(..., min_length=1, description="The user's message.")
    provider: LLMProvider | None = Field(
        default=None, description="Override the default LLM provider for this request only."
    )
    model: str | None = Field(
        default=None, description="Override the default model for this request only."
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Override the default sampling temperature for this request only."
    )


class Citation(BaseModel):
    """A source citation for a piece of retrieved podcast knowledge actually used in the response."""

    title: str = Field(..., description="Episode title.")
    guest: str | None = Field(default=None, description="Episode guest, if known.")
    youtube_url: str | None = Field(default=None, description="Episode YouTube URL, if known.")
    chunk_index: int = Field(..., description="Index of this chunk within its source transcript.")


class RetrievedChunkSchema(BaseModel):
    """A single retrieved transcript chunk, with its similarity score."""

    chunk_id: str
    text: str
    transcript_id: str
    similarity_score: float


class TokenUsage(BaseModel):
    """Token usage reported by the LLM provider, if available."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    """Response body for a chat exchange."""

    session_id: str = Field(..., description="The session this exchange belongs to.")
    response: str = Field(..., description="The assistant's response text.")
    retrieved_chunks: list[RetrievedChunkSchema] = Field(
        ..., description="Transcript chunks actually included in the prompt."
    )
    citations: list[Citation] = Field(..., description="Source citations for the retrieved chunks used.")
    provider: str = Field(..., description="LLM provider that generated the response.")
    model: str = Field(..., description="Model that generated the response.")
    latency_ms: float = Field(..., description="LLM generation latency, in milliseconds.")
    token_usage: TokenUsage = Field(..., description="Token usage for this exchange.")