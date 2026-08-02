"""
ChromaDB vector store wrapper.

Provides a thin, typed interface over a locally persisted ChromaDB
collection for storing and querying transcript chunk embeddings.
Contains no embedding-generation logic and no PostgreSQL access —
purely vector storage. Uses ChromaDB directly; no LangChain or
LlamaIndex.
"""

from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import ChromaError

from app.core.config import get_settings
from app.rag.chunker import Chunk
from app.rag.exceptions import VectorStoreError
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["ChromaVectorStore"]


class ChromaVectorStore:
    """Wraps a locally persisted ChromaDB collection for transcript chunk storage and retrieval."""

    def __init__(self, persist_directory: str | None = None, collection_name: str | None = None) -> None:
        """
        Args:
            persist_directory: Directory ChromaDB persists data to.
                Defaults to `Settings.CHROMA_PERSIST_DIRECTORY`.
            collection_name: Name of the Chroma collection to use.
                Defaults to `Settings.CHROMA_COLLECTION_NAME`.
        """
        settings = get_settings()
        self._persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self._collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self._client = chromadb.PersistentClient(path=self._persist_directory)
        self._collection: Collection = self.create_collection()

    def create_collection(self) -> Collection:
        """
        Gets or creates the configured Chroma collection.

        Returns:
            The Chroma `Collection` object.

        Raises:
            VectorStoreError: If the collection cannot be created.
        """
        try:
            collection = self._client.get_or_create_collection(name=self._collection_name)
        except ChromaError as exc:
            raise VectorStoreError(f"Failed to create/get collection '{self._collection_name}': {exc}") from exc
        log.debug("Using Chroma collection '{}' at {}", self._collection_name, self._persist_directory)
        return collection

    def get_collection(self) -> Collection:
        """
        Returns the currently active Chroma collection.

        Returns:
            The Chroma `Collection` object.
        """
        return self._collection

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        title: str,
        guest: str | None,
        youtube_url: str | None,
    ) -> None:
        """
        Upserts a transcript's chunks and their embeddings into the
        collection.

        Only the metadata required for display and filtering is
        stored per chunk: transcript_id, title, guest, youtube_url,
        chunk_index. Chunk text itself is stored as the Chroma
        "document".

        Args:
            chunks: The transcript's chunks, in order.
            embeddings: Embedding vectors, one per chunk, in the same
                order as `chunks`.
            title: The transcript's title.
            guest: The transcript's guest, if any.
            youtube_url: The transcript's source URL, if any.

        Raises:
            ValueError: If `chunks` and `embeddings` have different
                lengths.
            VectorStoreError: If the upsert operation fails.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")
        if not chunks:
            return

        try:
            self._collection.upsert(
                ids=[c.chunk_id for c in chunks],
                embeddings=embeddings,
                documents=[
    (
        f"Title: {title}\n"
        f"Guest: {guest or 'Unknown'}\n\n"
        f"{c.text}"
    )
    for c in chunks
],
                metadatas=[
                    {
                        "transcript_id": c.transcript_id,
                        "title": title,
                        "guest": guest or "",
                        "youtube_url": youtube_url or "",
                        "chunk_index": c.chunk_index,
                    }
                    for c in chunks
                ],
            )
        except ChromaError as exc:
            raise VectorStoreError(f"Failed to upsert chunks for transcript {chunks[0].transcript_id}: {exc}") from exc

        log.info("Upserted {} chunk(s) into Chroma for transcript {}", len(chunks), chunks[0].transcript_id)

    def delete_transcript(self, transcript_id: str) -> None:
        """
        Deletes all chunks belonging to a transcript from the
        collection.

        Args:
            transcript_id: The transcript's ID (string form).

        Raises:
            VectorStoreError: If the delete operation fails.
        """
        try:
            self._collection.delete(where={"transcript_id": transcript_id})
        except ChromaError as exc:
            raise VectorStoreError(f"Failed to delete chunks for transcript {transcript_id}: {exc}") from exc
        log.info("Deleted all chunks for transcript {} from Chroma", transcript_id)

    def query(self, query_embedding: list[float], top_k: int) -> dict[str, Any]:
        """
        Queries the collection for the most similar chunks to a given
        embedding.

        Args:
            query_embedding: The query's embedding vector.
            top_k: Maximum number of results to return.

        Returns:
            The raw ChromaDB query result dict (ids, documents,
            metadatas, distances).

        Raises:
            VectorStoreError: If the query operation fails.
        """
        try:
            return self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        except ChromaError as exc:
            raise VectorStoreError(f"Chroma query failed: {exc}") from exc

    def count(self) -> int:
        """
        Returns the total number of chunks currently stored in the
        collection.

        Returns:
            The chunk count.
        """
        return self._collection.count()

    def reset_collection(self) -> None:
        """
        Deletes and recreates the collection, removing all stored
        chunks. Intended for development/testing use, not normal
        ingestion runs.

        Raises:
            VectorStoreError: If the reset operation fails.
        """
        try:
            self._client.delete_collection(name=self._collection_name)
        except ChromaError as exc:
            raise VectorStoreError(f"Failed to reset collection '{self._collection_name}': {exc}") from exc
        self._collection = self.create_collection()
        log.warning("Collection '{}' was reset (all chunks deleted).", self._collection_name)