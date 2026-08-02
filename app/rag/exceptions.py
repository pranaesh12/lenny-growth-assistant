"""
RAG pipeline exceptions.

Custom exceptions raised across the ingestion and retrieval pipeline,
so failures at each stage (parsing, embedding, vector storage,
overall ingestion) are distinguishable and can be logged/handled
appropriately by the CLI script.
"""


class RAGError(Exception):
    """Base class for all RAG pipeline errors."""


class TranscriptParseError(RAGError):
    """Raised when a transcript file cannot be parsed (missing or malformed frontmatter)."""


class EmbeddingError(RAGError):
    """Raised when embedding generation fails or an unsupported provider is requested."""


class VectorStoreError(RAGError):
    """Raised when a ChromaDB operation fails."""


class IngestionError(RAGError):
    """Raised for ingestion-pipeline failures not covered by a more specific exception."""


__all__ = [
    "RAGError",
    "TranscriptParseError",
    "EmbeddingError",
    "VectorStoreError",
    "IngestionError",
]