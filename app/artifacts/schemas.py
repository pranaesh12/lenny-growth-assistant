"""
Typed request/response models and the artifact type registry.

`ArtifactKind` and `ARTIFACT_TEMPLATES` together are the extension
point for new artifact types: adding a new kind means adding one
enum member and one registry entry here — no changes to
`manager.py`, `generator.py`, or `prompt_builder.py` are needed.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.chat.schemas import TokenUsage
from app.core.constants import LLMProvider
from app.models.enums import ArtifactType, RenderFormat

__all__ = [
    "ArtifactKind",
    "ArtifactTemplate",
    "ARTIFACT_TEMPLATES",
    "ArtifactGenerationRequest",
    "ArtifactGenerationResponse",
]


class ArtifactKind(str, Enum):
    """The precise artifact template a user can request."""

    SUMMARY = "summary"
    MEETING_NOTES = "meeting_notes"
    ACTION_ITEMS = "action_items"
    STUDY_GUIDE = "study_guide"
    PRD = "prd"
    PRODUCT_STRATEGY = "product_strategy"
    GROWTH_STRATEGY = "growth_strategy"
    FEATURE_SPECIFICATION = "feature_specification"
    EXECUTIVE_SUMMARY = "executive_summary"
    DECISION_MATRIX = "decision_matrix"
    INTERVIEW_PREPARATION = "interview_preparation"
    LEARNING_PLAN = "learning_plan"
    MARKDOWN_NOTES = "markdown_notes"
    BLOG_DRAFT = "blog_draft"
    EMAIL_DRAFT = "email_draft"
    SOCIAL_MEDIA_POST = "social_media_post"


@dataclass
class ArtifactTemplate:
    """Defines how one `ArtifactKind` maps to a DB type, default title, and generation instructions."""

    db_type: ArtifactType
    default_title: str
    instructions: str


# The extension point: add a new ArtifactKind member above and a
# corresponding entry here to support a new artifact type. Nothing
# else in the artifact generation pipeline needs to change.
ARTIFACT_TEMPLATES: dict[ArtifactKind, ArtifactTemplate] = {
    ArtifactKind.SUMMARY: ArtifactTemplate(
        db_type=ArtifactType.SUMMARY,
        default_title="Summary",
        instructions="Write a concise summary of the conversation and relevant podcast context.",
    ),
    ArtifactKind.EXECUTIVE_SUMMARY: ArtifactTemplate(
        db_type=ArtifactType.SUMMARY,
        default_title="Executive Summary",
        instructions="Write a brief, high-level executive summary suitable for a busy stakeholder, focused on key takeaways and decisions.",
    ),
    ArtifactKind.MEETING_NOTES: ArtifactTemplate(
        db_type=ArtifactType.NOTES,
        default_title="Meeting Notes",
        instructions="Write structured meeting notes capturing key discussion points, decisions, and open questions.",
    ),
    ArtifactKind.ACTION_ITEMS: ArtifactTemplate(
        db_type=ArtifactType.NOTES,
        default_title="Action Items",
        instructions="Extract a clear, actionable checklist of next steps from the conversation, with owners noted where mentioned.",
    ),
    ArtifactKind.STUDY_GUIDE: ArtifactTemplate(
        db_type=ArtifactType.NOTES,
        default_title="Study Guide",
        instructions="Write a study guide covering the key concepts discussed, organized for someone learning the topic.",
    ),
    ArtifactKind.LEARNING_PLAN: ArtifactTemplate(
        db_type=ArtifactType.NOTES,
        default_title="Learning Plan",
        instructions="Write a structured learning plan with concrete steps, based on the topics discussed.",
    ),
    ArtifactKind.MARKDOWN_NOTES: ArtifactTemplate(
        db_type=ArtifactType.NOTES,
        default_title="Notes",
        instructions="Write freeform markdown notes capturing the key ideas from the conversation.",
    ),
    ArtifactKind.PRD: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Product Requirement Document",
        instructions="Write a Product Requirement Document (PRD) with sections for Problem, Goals, Non-Goals, User Stories, Requirements, and Success Metrics, grounded in the conversation.",
    ),
    ArtifactKind.PRODUCT_STRATEGY: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Product Strategy",
        instructions="Write a product strategy document covering vision, target users, key bets, and success metrics.",
    ),
    ArtifactKind.GROWTH_STRATEGY: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Growth Strategy",
        instructions="Write a growth strategy document covering acquisition, activation, retention levers, and specific tactics grounded in the podcast context provided.",
    ),
    ArtifactKind.FEATURE_SPECIFICATION: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Feature Specification",
        instructions="Write a detailed feature specification covering the problem, proposed solution, edge cases, and acceptance criteria.",
    ),
    ArtifactKind.DECISION_MATRIX: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Decision Matrix",
        instructions="Write a decision matrix (as a markdown table) comparing the options discussed against relevant criteria, with a recommendation.",
    ),
    ArtifactKind.INTERVIEW_PREPARATION: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Interview Preparation",
        instructions="Write interview preparation notes, including likely questions and strong talking points, based on the conversation.",
    ),
    ArtifactKind.BLOG_DRAFT: ArtifactTemplate(
        db_type=ArtifactType.ESSAY,
        default_title="Blog Draft",
        instructions="Write a blog post draft with a compelling hook, clear structure, and a strong conclusion, based on the conversation and podcast context.",
    ),
    ArtifactKind.EMAIL_DRAFT: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Email Draft",
        instructions="Write a clear, professional email draft based on the conversation, with an appropriate subject line and tone.",
    ),
    ArtifactKind.SOCIAL_MEDIA_POST: ArtifactTemplate(
        db_type=ArtifactType.MARKDOWN_DOC,
        default_title="Social Media Post",
        instructions="Write a concise, engaging social media post distilling the key insight from the conversation.",
    ),
}


class ArtifactGenerationRequest(BaseModel):
    """Request body for generating an artifact from a session's conversation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_f83ac91d3b2e4a10",
                "artifact_type": "growth_strategy",
            }
        }
    )

    session_id: str = Field(..., description="The session to generate this artifact from.")
    artifact_type: ArtifactKind = Field(..., description="Which artifact template to generate.")
    title: str | None = Field(default=None, min_length=1, max_length=200, description="Override the template's default title.")
    instructions: str | None = Field(default=None, description="Additional user instructions to guide generation.")
    provider: LLMProvider | None = Field(default=None, description="Override the default artifact provider for this request only.")
    model: str | None = Field(default=None, description="Override the default artifact model for this request only.")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Override the default artifact temperature for this request only.")


class ArtifactGenerationResponse(BaseModel):
    """Response body for a generated artifact."""

    artifact_id: str = Field(..., description="ID of the newly created, persisted artifact.")
    session_id: str = Field(..., description="The session this artifact belongs to.")
    artifact_type: ArtifactKind = Field(..., description="The artifact template used.")
    title: str = Field(..., description="The artifact's title.")
    content: str = Field(..., description="The generated artifact content.")
    provider: str = Field(..., description="LLM provider that generated this artifact.")
    model: str = Field(..., description="Model that generated this artifact.")
    created_at: datetime = Field(..., description="UTC timestamp of artifact creation.")
    latency_ms: float = Field(..., description="LLM generation latency, in milliseconds.")
    token_usage: TokenUsage = Field(..., description="Token usage for this generation.")