"""
Pydantic schemas for the Message API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MessageRole, ProviderType

__all__ = ["MessageCreate", "MessageResponse", "MessageListResponse"]


class MessageCreate(BaseModel):
    """Request body for creating a new message within a session."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "What's a good essay hook for a post about focus?",
            }
        }
    )

    role: MessageRole = Field(..., description="Who authored the message: user, assistant, or system.")
    content: str = Field(..., min_length=1, description="Full message text. Must not be blank.")
    content_type: str = Field(default="markdown", max_length=50, description="Render format of the content.")
    provider_used: ProviderType | None = Field(
        default=None,
        description="LLM provider that generated this message. Only valid for assistant messages.",
    )
    artifact_id: str | None = Field(
        default=None, description="Optional artifact this message produced or references."
    )


class MessageResponse(BaseModel):
    """Response body representing a single message."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Message identifier, e.g. msg_84ab7c12e93f4d21.")
    session_id: str = Field(..., description="The parent session this message belongs to.")
    role: MessageRole = Field(..., description="Who authored the message.")
    content: str = Field(..., description="Full message text.")
    content_type: str = Field(..., description="Render format of the content.")
    provider_used: ProviderType | None = Field(default=None, description="Provider that generated the message, if applicable.")
    artifact_id: str | None = Field(default=None, description="Artifact this message references, if any.")
    created_at: datetime = Field(..., description="UTC timestamp of message creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of the last modification.")


class MessageListResponse(BaseModel):
    """Response body representing a list of messages."""

    messages: list[MessageResponse] = Field(..., description="Messages, in chronological order (oldest first).")
    count: int = Field(..., description="Number of messages in this response.")