"""
Pydantic schemas for the Session API.

Defines the request and response shapes exposed by
`app/api/v1/endpoints/sessions.py`. These schemas are the API
contract layer — they never touch SQLAlchemy models directly; the
API layer converts between `Session` ORM instances and these schemas
at the boundary.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProviderType

__all__ = ["SessionCreate", "SessionUpdate", "SessionResponse", "SessionListResponse"]


class SessionCreate(BaseModel):
    """Request body for creating a new session."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "New Chat"}}
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Initial session title. If omitted, the session is "
            "created with the default title 'New Session'."
        ),
    )


class SessionUpdate(BaseModel):
    """Request body for renaming a session."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Growth Ideas"}}
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="New session title.",
    )


class SessionResponse(BaseModel):
    """Response body representing a single session."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Session identifier, e.g. sess_f83ac91d3b2e4a10.")
    title: str = Field(..., description="Human-readable session title.")
    archived: bool = Field(..., description="Whether the session has been archived.")
    last_provider_used: ProviderType | None = Field(
        default=None, description="Most recent LLM provider used in this session, if any."
    )
    created_at: datetime = Field(..., description="UTC timestamp of session creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of the last modification.")


class SessionListResponse(BaseModel):
    """Response body representing a list of sessions."""

    sessions: list[SessionResponse] = Field(..., description="Sessions, newest first.")
    count: int = Field(..., description="Number of sessions in this response.")