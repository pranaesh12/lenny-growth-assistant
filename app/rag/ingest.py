"""
Ingestion pipeline orchestration.

Wires together the loader, parser, chunker, embedding provider, and
vector store, plus the existing PostgreSQL Repository/Service layers,
into a single per-transcript ingestion operation:

    load -> parse -> compute deterministic transcript_id ->
    check PostgreSQL (skip if exists) -> save metadata ->
    chunk -> embed -> upsert (ChromaDB) -> update chunk_count -> log

Contains no CLI logic (see scripts/ingest_transcripts.py).

Note on Repository vs. Service usage: transcript metadata creation
uses `TranscriptRepository.create()` (the generic, inherited
BaseRepository method) directly, rather than
`TranscriptService.create_metadata()`, because the deterministic
`transcript_id` computed here must be set explicitly at insert time,
and the existing service method (Phase 8) does not accept an
explicit ID parameter. This is still the Repository Layer, not raw
SQLAlchemy — no `Session`/query construct is touched directly.
Existence checks and chunk-count updates DO go through
`TranscriptService`, as normal.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.rag.chunker import chunk_transcript_text
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.exceptions import IngestionError
from app.rag.parser import parse_transcript_file
from app.rag.vector_store import ChromaVectorStore
from app.repositories.transcript_repository import TranscriptRepository
from app.services.exceptions import NotFoundError
from app.services.transcript_service import TranscriptService
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["ingest_transcript_file"]


def ingest_transcript_file(
    path: Path,
    transcript_repository: TranscriptRepository,
    transcript_service: TranscriptService,
    vector_store: ChromaVectorStore | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[str, bool]:
    """
    Ingests a single transcript file end-to-end, skipping it if
    already ingested.

    Args:
        path: Path to the transcript file.
        transcript_repository: Repository used only for the initial
            metadata insert (to set an explicit deterministic ID).
        transcript_service: Service used for existence checks and
            chunk-count updates.
        vector_store: Vector store to upsert chunks into. Defaults to
            a new `ChromaVectorStore`.
        embedding_provider: Provider used to embed chunks. Defaults
            to `get_embedding_provider()`.

    Returns:
        A tuple of (transcript_id as string, was_skipped). If
        `was_skipped` is True, the transcript was already ingested
        and no work was performed.

    Raises:
        TranscriptParseError: If the file cannot be parsed.
        EmbeddingError: If embedding generation fails.
        VectorStoreError: If the ChromaDB upsert fails.
        IngestionError: For any other ingestion failure.
    """
    settings = get_settings()
    vector_store = vector_store or ChromaVectorStore()
    embedding_provider = embedding_provider or get_embedding_provider()

    start_time = time.perf_counter()

    parsed = parse_transcript_file(path)
    transcript_id_str = str(parsed.transcript_id)
    log.info("Loaded transcript '{}' (id={}) from {}", parsed.title, transcript_id_str, path)

    try:
        transcript_service.get_transcript_metadata(transcript_id_str)
        log.info("Transcript {} already ingested — skipping.", transcript_id_str)
        return transcript_id_str, True
    except NotFoundError:
        pass  # Not yet ingested — proceed.

    try:
        transcript_repository.create(
            id=parsed.transcript_id,
            title=parsed.title,
            ingested_at=datetime.now(timezone.utc),
            source_url=parsed.youtube_url,
            chunk_count=0,
            summary=parsed.description,
        )
        log.info("Saved metadata for transcript {} to PostgreSQL", transcript_id_str)
    except Exception as exc:
        raise IngestionError(f"Failed to save metadata for transcript {transcript_id_str}: {exc}") from exc

    chunks = chunk_transcript_text(
        text=parsed.transcript_text,
        transcript_id=transcript_id_str,
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
    )
    log.info("Chunked transcript {} into {} chunk(s)", transcript_id_str, len(chunks))

    documents = [
    (
        f"Title: {parsed.title}\n"
        f"Guest: {parsed.guest}\n\n"
        f"Transcript:\n{chunk.text}"
    )
    for chunk in chunks
]

    embeddings = embedding_provider.embed_texts(documents)
    log.info("Generated {} embedding(s) for transcript {}", len(embeddings), transcript_id_str)

    vector_store.upsert_chunks(
        chunks=chunks,
        embeddings=embeddings,
        title=parsed.title,
        guest=parsed.guest,
        youtube_url=parsed.youtube_url,
    )

    transcript_service.update_chunk_count(transcript_id_str, len(chunks))

    elapsed = time.perf_counter() - start_time
    log.info("Ingested transcript {} ('{}') in {:.2f}s", transcript_id_str, parsed.title, elapsed)

    return transcript_id_str, False