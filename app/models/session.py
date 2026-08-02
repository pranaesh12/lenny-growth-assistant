"""
Session model.

Represents a single chat/growth-assistant session — the top-level
container that messages and generated artifacts belong to. This is
the first concrete domain model in the project; `Message` and
`Artifact` (Phase 6.3+) will each declare a `back_populates`
relationship pointing back to this class.
"""

import secrets

from sqlalchemy import Boolean, Enum as SQLEnum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ProviderType

__all__ = ["Session", "generate_session_id"]


def generate_session_id() -> str:
    """
    Generates a unique, URL-safe identifier for a new `Session` row.

    Produces IDs in the format `sess_<16 hex chars>`, e.g.
    `sess_f83ac91d3b2e4a10`. A human-readable prefix (`sess_`) is
    used instead of a raw UUID so IDs are self-describing when they
    appear in logs, URLs, or API responses — at a glance it's
    unambiguous that the identifier refers to a session, as opposed
    to a message, artifact, or other entity.

    `secrets.token_hex(8)` is used (rather than `uuid.uuid4()`)
    because it draws from the OS's cryptographically secure random
    source and produces a shorter, purely hexadecimal suffix with no
    formatting characters (no dashes), which keeps the resulting ID
    compact and simple to use directly in URL paths.

    Returns:
        str: A new identifier in the form `sess_<16 hex chars>`.
    """
    return f"sess_{secrets.token_hex(8)}"


class Session(Base, TimestampMixin):
    """
    A single chat/growth-assistant session.

    A `Session` is the top-level conversational container: it groups
    an ordered sequence of `Message` records and any `Artifact`
    records (essays, markdown documents, HTML snippets) generated
    during the conversation. Deleting a session cascades to delete
    all of its messages and artifacts — a session and its contents
    share the same lifecycle.

    Inherits `created_at` / `updated_at` from `TimestampMixin`; do
    not redefine them here.
    """

    __tablename__ = "sessions"

    __table_args__ = (
        # Speeds up session search/filtering by title, e.g. a sidebar
        # search box or 'find session by name' query.
        Index("ix_sessions_title", "title", postgresql_using="btree"),
        # Speeds up sorting/filtering sessions by recency, e.g. a
        # 'most recently active sessions' list view — the most common
        # ordering for a session sidebar.
        Index("ix_sessions_updated_at", "updated_at"),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=generate_session_id,
        doc="Primary key. Format: sess_<16 hex chars>, e.g. sess_f83ac91d3b2e4a10.",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="New Session",
        server_default="New Session",
        doc="Human-readable session title, shown in UI listings. Max 200 chars.",
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether the session has been archived (hidden from the active session list).",
    )

    last_provider_used: Mapped[ProviderType | None] = mapped_column(
        SQLEnum(
            ProviderType,
            name="provider_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
        doc="Most recent LLM provider used to respond within this session, if any.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    # `Message` and `Artifact` do not exist yet (Phase 6.3+). Forward
    # references (string class names) are used so this module can be
    # imported now without a circular or missing-class import error —
    # SQLAlchemy resolves string-based relationship targets lazily,
    # at mapper configuration time, not at class-definition time.
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="All messages belonging to this session, ordered by insertion.",
    )

    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="All artifacts (essays, markdown docs, HTML snippets) generated in this session.",
    )

    def __repr__(self) -> str:
        """Returns a concise, debug-friendly representation of the session."""
        return f"Session(id={self.id!r}, title={self.title!r}, archived={self.archived!r})"