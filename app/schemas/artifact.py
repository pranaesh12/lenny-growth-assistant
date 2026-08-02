"""
Pydantic schemas for the Artifact API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArtifactType, RenderFormat

__all__ = ["ArtifactCreate", "ArtifactResponse", "ArtifactListResponse"]


class ArtifactCreate(BaseModel):
    """Request body for creating a new artifact."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_f83ac91d3b2e4a10",
                "title": "Focus Essay Draft",
                "type": "essay",
                "render_format": "markdown",
                "content": "# Focus\n\nFocus is the ability to...",
            }
        }
    )

    session_id: str = Field(..., description="The parent session this artifact belongs to.")
    title: str = Field(..., min_length=1, max_length=200, description="Human-readable artifact title.")
    type: ArtifactType = Field(..., description="The kind of content this artifact represents.")
    render_format: RenderFormat = Field(..., description="Markup format the content should be rendered as.")
    content: str = Field(..., min_length=1, description="Full artifact content.")


class ArtifactResponse(BaseModel):
    """Response body representing a single artifact."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Artifact identifier, e.g. art_f83ac91d3b2e4a10.")
    session_id: str = Field(..., description="The parent session this artifact belongs to.")
    title: str = Field(..., description="Human-readable artifact title.")
    type: ArtifactType = Field(..., description="The kind of content this artifact represents.")
    render_format: RenderFormat = Field(..., description="Markup format the content is rendered as.")
    content: str = Field(..., description="Full artifact content.")
    created_at: datetime = Field(..., description="UTC timestamp of artifact creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of the last modification.")
    kind: str | None = Field(default=None, description="Precise artifact template used (e.g. 'prd'), if generated via the artifact generation pipeline.")


class ArtifactListResponse(BaseModel):
    """Response body representing a list of artifacts."""

    artifacts: list[ArtifactResponse] = Field(..., description="Artifacts, most recently updated first.")
    count: int = Field(..., description="Number of artifacts in this response.")