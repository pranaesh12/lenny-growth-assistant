"""
Transcript repository.

Provides database access for `Transcript` metadata rows, on top of
the common CRUD operations from `BaseRepository`. Only metadata is
handled here — transcript chunks and embeddings live in ChromaDB,
which this repository has no knowledge of.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as ORMSession

from app.models.transcript import Transcript
from app.repositories.base import BaseRepository


class TranscriptRepository(BaseRepository[Transcript]):
    """Repository for `Transcript` metadata database access."""

    def __init__(self, db: ORMSession) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session.
        """
        super().__init__(db, Transcript)

    def create_transcript_metadata(
        self,
        title: str,
        ingested_at: datetime,
        source_url: str | None = None,
        chunk_count: int = 0,
        summary: str | None = None,
        **extra_fields: Any,
    ) -> Transcript:
        """
        Creates and persists a new transcript metadata row.

        Args:
            title: Human-readable transcript title.
            ingested_at: Timestamp of when the transcript's chunks
                were embedded into ChromaDB.
            source_url: Optional URL of the original source.
            chunk_count: Number of chunks the transcript was split
                into. Defaults to 0.
            summary: Optional summary of the transcript's content.
            **extra_fields: Any additional column values to set.

        Returns:
            The newly created, persisted `Transcript` metadata row.
        """
        return self.create(
            title=title,
            ingested_at=ingested_at,
            source_url=source_url,
            chunk_count=chunk_count,
            summary=summary,
            **extra_fields,
        )

    def get_by_source_url(self, source_url: str) -> Transcript | None:
        """
        Fetches a transcript metadata row by its source URL.

        Args:
            source_url: The original source URL to look up.

        Returns:
            The matching `Transcript`, or None if no row has that
            source URL.
        """
        statement = select(Transcript).where(Transcript.source_url == source_url)
        return self.db.execute(statement).scalar_one_or_none()