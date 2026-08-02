"""
Transcript text chunker.

Splits transcript body text into fixed-size, overlapping, ordered
chunks with deterministic IDs. Contains no I/O — pure text splitting.
"""

from dataclasses import dataclass

from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["Chunk", "chunk_transcript_text"]


@dataclass
class Chunk:
    """A single chunk of transcript text, ready for embedding."""

    chunk_id: str
    transcript_id: str
    chunk_index: int
    text: str


def chunk_transcript_text(
    text: str,
    transcript_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """
    Splits text into overlapping, ordered chunks with deterministic IDs.

    Args:
        text: The full transcript body text to split.
        transcript_id: The transcript's ID (string form), used to
            build each chunk's deterministic ID.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of characters each chunk overlaps with
            the previous one, to preserve context across boundaries.

    Returns:
        A list of `Chunk` objects, in order. Each `chunk_id` is
        `"<transcript_id>_<chunk_index:04d>"` — deterministic and
        stable across re-ingestion runs of the same transcript.

    Raises:
        ValueError: If `chunk_overlap` is greater than or equal to
            `chunk_size`.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk_text = text[start:end]
        chunks.append(
            Chunk(
                chunk_id=f"{transcript_id}_{index:04d}",
                transcript_id=transcript_id,
                chunk_index=index,
                text=chunk_text,
            )
        )
        if end >= text_length:
            break
        start = end - chunk_overlap
        index += 1

    log.debug("Split transcript {} into {} chunk(s)", transcript_id, len(chunks))
    return chunks