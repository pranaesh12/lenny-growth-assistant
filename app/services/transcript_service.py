"""
Transcript service.

Contains business logic for managing transcript metadata. Uses only
`TranscriptRepository` for data access — never touches SQLAlchemy
models or query constructs directly. Actual transcript chunks and
embeddings live in ChromaDB and are entirely outside this service's
concern; it only manages the PostgreSQL metadata record.
"""

from datetime import datetime

from app.models.transcript import Transcript
from app.repositories.transcript_repository import TranscriptRepository
from app.services.exceptions import NotFoundError, ValidationError


class TranscriptService:
    """Business logic for transcript metadata management."""

    def __init__(self, repository: TranscriptRepository) -> None:
        """
        Args:
            repository: Repository providing transcript metadata
                data access.
        """
        self.repository = repository

    def create_metadata(
        self,
        title: str,
        ingested_at: datetime,
        source_url: str | None = None,
        chunk_count: int = 0,
        summary: str | None = None,
    ) -> Transcript:
        """
        Creates a new transcript metadata row.

        Args:
            title: Human-readable transcript title. Must not be
                blank.
            ingested_at: Timestamp of when the transcript's chunks
                were embedded into ChromaDB.
            source_url: Optional URL of the original source. If
                provided, must not already be in use by another
                transcript.
            chunk_count: Number of chunks the transcript was split
                into. Must be non-negative.
            summary: Optional summary of the transcript's content.

        Returns:
            The newly created `Transcript` metadata row.

        Raises:
            ValidationError: If `title` is blank, `chunk_count` is
                negative, or `source_url` is already used by another
                transcript.
        """
        title = title.strip()
        if not title:
            raise ValidationError("Transcript title must not be blank.")
        if len(title) > 255:
            raise ValidationError("Transcript title must not exceed 255 characters.")

        if chunk_count < 0:
            raise ValidationError("chunk_count must not be negative.")

        if source_url:
            existing = self.repository.get_by_source_url(source_url)
            if existing is not None:
                raise ValidationError(
                    f"A transcript with source_url '{source_url}' already exists "
                    f"(id={existing.id})."
                )

        return self.repository.create_transcript_metadata(
            title=title,
            ingested_at=ingested_at,
            source_url=source_url,
            chunk_count=chunk_count,
            summary=summary,
        )

    def get_transcript_metadata(self, transcript_id: str) -> Transcript:
        """
        Fetches a single transcript metadata row by ID.

        Args:
            transcript_id: The transcript's primary key.

        Returns:
            The matching `Transcript`.

        Raises:
            NotFoundError: If no transcript exists with that ID.
        """
        transcript = self.repository.get_by_id(transcript_id)
        if transcript is None:
            raise NotFoundError(f"Transcript '{transcript_id}' was not found.")
        return transcript

    def list_transcripts(self, skip: int = 0, limit: int = 100) -> list[Transcript]:
        """
        Lists transcript metadata rows with pagination.

        Args:
            skip: Number of rows to skip.
            limit: Maximum number of rows to return.

        Returns:
            A list of `Transcript` rows.

        Raises:
            ValidationError: If `limit` is not a positive integer or
                `skip` is negative.
        """
        if limit <= 0:
            raise ValidationError("limit must be a positive integer.")
        if skip < 0:
            raise ValidationError("skip must not be negative.")
        return self.repository.get_all(skip=skip, limit=limit)

    def update_chunk_count(self, transcript_id: str, chunk_count: int) -> Transcript:
        """
        Updates a transcript's chunk count, typically after
        (re-)ingesting its content into ChromaDB.

        Args:
            transcript_id: The transcript's primary key.
            chunk_count: The new chunk count. Must be non-negative.

        Returns:
            The updated `Transcript`.

        Raises:
            NotFoundError: If no transcript exists with that ID.
            ValidationError: If `chunk_count` is negative.
        """
        self.get_transcript_metadata(transcript_id)

        if chunk_count < 0:
            raise ValidationError("chunk_count must not be negative.")

        updated = self.repository.update(transcript_id, chunk_count=chunk_count)
        assert updated is not None
        return updated