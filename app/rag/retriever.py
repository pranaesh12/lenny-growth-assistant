"""
Retrieval interface.

Combines the embedding provider and vector store to answer
"find the most relevant transcript chunks for this query" — the
read-side of the RAG pipeline. Contains no completion/prompt-building
or LLM-calling logic (out of scope per Phase 11).
"""

from dataclasses import dataclass

from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.vector_store import ChromaVectorStore
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["RetrievedChunk", "Retriever"]


@dataclass
class RetrievedChunk:
    """A single retrieved chunk with its metadata and similarity score."""

    chunk_id: str
    text: str
    transcript_id: str
    title: str
    guest: str | None
    youtube_url: str | None
    chunk_index: int
    similarity_score: float


class Retriever:
    """Retrieves the most relevant transcript chunks for a query. Retrieval only — no LLM calls."""

    def __init__(
        self,
        vector_store: ChromaVectorStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """
        Args:
            vector_store: Vector store to query. Defaults to a new
                `ChromaVectorStore` using configured settings.
            embedding_provider: Provider used to embed the query.
                Defaults to `get_embedding_provider()`.
        """
        self._vector_store = vector_store or ChromaVectorStore()
        self._embedding_provider = embedding_provider or get_embedding_provider()

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """
        Retrieves the top matching transcript chunks for a query.

        Args:
            query: The natural-language query text.
            top_k: Maximum number of chunks to return.

        Returns:
            A list of `RetrievedChunk` objects, ordered by relevance
            (most similar first).
        """
        query_embedding = self._embedding_provider.embed_texts([query])[0]
        raw_results = self._vector_store.query(query_embedding, top_k=top_k)

        ids = raw_results.get("ids", [[]])[0]
        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        results: list[RetrievedChunk] = []
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            # ChromaDB returns a distance (lower = more similar) by
            # default; converting to a similarity score (higher =
            # more similar) is more intuitive for callers.
            similarity_score = 1.0 / (1.0 + distance)
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=document,
                    transcript_id=metadata.get("transcript_id", ""),
                    title=metadata.get("title", ""),
                    guest=metadata.get("guest") or None,
                    youtube_url=metadata.get("youtube_url") or None,
                    chunk_index=metadata.get("chunk_index", 0),
                    similarity_score=similarity_score,
                )
            )

        log.info("Retrieved {} chunk(s) for query", len(results))
        return results