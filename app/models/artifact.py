"""
Artifact model.

Represents a standalone generated content object — an essay, markdown
document, HTML snippet, notes, or summary — produced during a chat
session. Artifacts are independent resources: they belong to exactly
one `Session`, and any `Message` may optionally reference the
artifact it produced via `Message.artifact_id`.
"""

import secrets

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ArtifactType, RenderFormat

__all__ = ["Artifact", "generate_artifact_id"]


def generate_artifact_id() -> str:
    """
    Generates a unique, URL-safe identifier for a new `Artifact` row.

    Produces IDs in the format `art_<16 hex chars>`, e.g.
    `art_f83ac91d3b2e4a10`. Follows the same identifier strategy as
    `generate_session_id` and `generate_message_id`: a human-readable
    prefix (`art_`) makes the entity type obvious at a glance in
    logs, URLs, and API payloads, and `secrets.token_hex(8)` draws
    from the OS's cryptographically secure random source to produce
    a compact, dash-free, purely hexadecimal suffix.

    This replaces the native-UUID primary key originally specified
    for `Artifact`, in favor of matching the prefixed string-ID
    convention used consistently by `Session` and `Message` — see
    the Phase 6.8 schema verification for the reasoning (keeps
    `Message.artifact_id`'s foreign key type-compatible, and keeps
    ID formatting consistent and self-describing across the API).

    Returns:
        str: A new identifier in the form `art_<16 hex chars>`.
    """
    return f"art_{secrets.token_hex(8)}"


class Artifact(Base, TimestampMixin):
    """
    A standalone piece of generated content belonging to a session.

    Examples include a Ship30-style essay, a markdown document, an
    HTML snippet, freeform notes, or a summary. Each artifact belongs
    to exactly one `Session` and is deleted automatically when its
    parent session is deleted (see `cascade="all, delete-orphan"` on
    `Session.artifacts`, configured in Phase 6.2).

    Zero or more `Message` rows may reference a given artifact via
    `Message.artifact_id` — e.g. the assistant message that generated
    it, or later messages that discuss it.

    Inherits `created_at` / `updated_at` from `TimestampMixin`; do
    not redefine them here.
    """

    __tablename__ = "artifacts"

    __table_args__ = (
        # Speeds up the most frequent query pattern: fetching all
        # artifacts belonging to a given session (e.g. an artifacts
        # panel/sidebar for the active session).
        Index("ix_artifacts_session_id", "session_id"),
        # Speeds up filtering artifacts by type, e.g. listing only
        # essays or only markdown documents across a session or the
        # whole workspace.
        Index("ix_artifacts_type", "type"),
        # Speeds up sorting artifacts by recency, e.g. a 'recently
        # edited artifacts' view.
        Index("ix_artifacts_updated_at", "updated_at"),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=generate_artifact_id,
        doc="Primary key. Format: art_<16 hex chars>, e.g. art_f83ac91d3b2e4a10.",
    )

    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the parent session this artifact belongs to.",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable artifact title. Max 200 chars.",
    )

    type: Mapped[ArtifactType] = mapped_column(
        SQLEnum(
            ArtifactType,
            name="artifact_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        doc="The kind of content this artifact represents (essay, markdown_doc, html_snippet, notes, summary).",
    )

    render_format: Mapped[RenderFormat] = mapped_column(
        SQLEnum(
            RenderFormat,
            name="render_format",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        doc="Markup format the artifact's content should be rendered as (markdown or html).",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full artifact content.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="artifacts",
        lazy="selectin",
        doc="The parent session this artifact belongs to.",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="artifact",
        lazy="selectin",
        doc="All messages that reference this artifact.",
    )

    kind: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc=(
            "Precise artifact template requested (e.g. 'prd', 'growth_strategy'), "
            "distinct from the structural `type` column above. Nullable for "
            "backward compatibility with artifacts created before this column existed."
        ),
    )

    def __repr__(self) -> str:
        """Returns a concise, debug-friendly representation of the artifact."""
        return f"Artifact(id={self.id!r}, session_id={self.session_id!r}, type={self.type!r})"