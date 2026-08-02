"""
Transcript model.

Stores metadata ONLY for transcripts used by the RAG system. The
actual transcript chunks and their vector embeddings live in
ChromaDB, not PostgreSQL — this table exists purely so the frontend
can list available transcripts, display metadata about them, and
filter RAG retrieval by transcript, without querying ChromaDB just
to answer "what transcripts exist?".

This model is intentionally simple and has no relationships to
`Session`, `Message`, or `Artifact` — a transcript is a standalone
knowledge-base resource, not part of a conversation's object graph.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy import Uuid as SQLUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

__all__ = ["Transcript"]


class Transcript(Base, TimestampMixin):
    """
    Metadata record for a transcript ingested into the RAG system.

    Represents a source document (e.g. a podcast transcript, article,
    or note set) that has been chunked and embedded into ChromaDB.
    This row does NOT contain the transcript's actual chunk text or
    embeddings — only descriptive metadata used for listing,
    filtering, and display purposes.

    Inherits `created_at` / `updated_at` from `TimestampMixin`; do
    not redefine them here. `ingested_at` is distinct from
    `created_at`: `created_at` reflects when this metadata row was
    written to PostgreSQL, while `ingested_at` reflects when the
    transcript's content was actually processed into ChromaDB —
    these may differ if metadata is created before/after ingestion
    completes.
    """

    __tablename__ = "transcripts"

    __table_args__ = (
        CheckConstraint(
            "chunk_count >= 0",
            name="ck_transcripts_chunk_count_non_negative",
        ),
        # Speeds up searching/filtering transcripts by title, e.g. a
        # transcript picker or search box in the UI.
        Index("ix_transcripts_title", "title"),
        # Speeds up sorting/filtering transcripts by ingestion recency,
        # e.g. a 'recently added transcripts' list.
        Index("ix_transcripts_ingested_at", "ingested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key. Native UUID, generated client-side via uuid.uuid4() at insert time.",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable transcript title. Required, max 255 chars.",
    )

    source_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional URL pointing to the original source of the transcript. Max 500 chars.",
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc=(
            "Number of chunks this transcript was split into for "
            "embedding into ChromaDB. Defaults to 0 (e.g. before "
            "ingestion has run); enforced non-negative via a check "
            "constraint."
        ),
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional human- or AI-generated summary of the transcript's content.",
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc=(
            "UTC timestamp of when this transcript's chunks were "
            "embedded into ChromaDB. Distinct from `created_at` "
            "(when this metadata row itself was created)."
        ),
    )

    def __repr__(self) -> str:
        """Returns a concise, debug-friendly representation of the transcript."""
        return f"Transcript(id={self.id!r}, title={self.title!r}, chunk_count={self.chunk_count!r})"