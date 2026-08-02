"""
Pydantic schemas for the Transcript metadata API.

These schemas expose ONLY PostgreSQL metadata about transcripts.
Transcript chunks and embeddings live in ChromaDB and are never
exposed through this API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TranscriptResponse", "TranscriptListResponse"]


class TranscriptResponse(BaseModel):
    """Response body representing a single transcript's metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Transcript identifier (UUID).")
    title: str = Field(..., description="Human-readable transcript title.")
    source_url: str | None = Field(default=None, description="Original source URL, if any.")
    chunk_count: int = Field(..., description="Number of chunks this transcript was split into for ChromaDB.")
    summary: str | None = Field(default=None, description="Optional summary of the transcript's content.")
    ingested_at: datetime = Field(..., description="UTC timestamp of when the transcript was embedded into ChromaDB.")
    created_at: datetime = Field(..., description="UTC timestamp of when this metadata row was created.")
    updated_at: datetime = Field(..., description="UTC timestamp of the last modification.")


class TranscriptListResponse(BaseModel):
    """Response body representing a list of transcript metadata rows."""

    transcripts: list[TranscriptResponse] = Field(..., description="Transcript metadata rows.")
    count: int = Field(..., description="Number of transcripts in this response.")