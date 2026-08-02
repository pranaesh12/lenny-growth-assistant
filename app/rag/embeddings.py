"""
Embedding provider abstraction.

Defines a provider-agnostic interface for generating text embeddings
in batches, with Ollama as the default local provider and OpenAI kept
as an optional alternative. Additional providers (HuggingFace,
VoyageAI, Gemini) can be added by implementing `EmbeddingProvider` and
registering them in `_PROVIDER_REGISTRY`, without changing any
ingestion or retrieval code.
"""

from abc import ABC, abstractmethod

import requests
from requests.exceptions import RequestException

from app.core.config import get_settings
from app.rag.exceptions import EmbeddingError
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = [
    "EmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
]


class EmbeddingProvider(ABC):
    """Abstract interface for generating text embeddings in batches."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a batch of texts.

        Args:
            texts: The texts to embed (e.g. transcript chunks, or a
                single-element list for a retrieval query).

        Returns:
            A list of embedding vectors, in the same order as `texts`.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        raise NotImplementedError


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider backed by a local Ollama server.

    Uses Ollama's batch-capable `/api/embed` endpoint (Ollama >= 0.3),
    which accepts a list of input strings and returns one embedding
    vector per input, in order. Requests are chunked into batches of
    `batch_size` so very large ingestion runs don't send oversized
    payloads in a single call.
    """

    def __init__(self, base_url: str, model: str, batch_size: int) -> None:
        """
        Args:
            base_url: Base URL of the running Ollama server
                (e.g. "http://localhost:11434").
            model: Embedding model name pulled into Ollama
                (e.g. "nomic-embed-text").
            batch_size: Maximum number of texts sent per request.
        """
        self._endpoint = f"{base_url.rstrip('/')}/api/embed"
        self._model = model
        self._batch_size = batch_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of texts, chunked into request-sized batches."""
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                response = requests.post(
                    self._endpoint,
                    json={"model": self._model, "input": batch},
                    timeout=120,
                )
                response.raise_for_status()
            except RequestException as exc:
                raise EmbeddingError(
                    f"Ollama embedding request failed at {self._endpoint}: {exc}"
                ) from exc

            payload = response.json()
            batch_embeddings = payload.get("embeddings")
            if batch_embeddings is None:
                raise EmbeddingError(
                    f"Ollama response missing 'embeddings' field: {payload}"
                )
            if len(batch_embeddings) != len(batch):
                raise EmbeddingError(
                    f"Ollama returned {len(batch_embeddings)} embedding(s) for "
                    f"{len(batch)} input(s) — response is out of order or incomplete."
                )

            embeddings.extend(batch_embeddings)
            log.debug("Embedded batch of {} text(s) via Ollama ({})", len(batch), self._model)

        return embeddings


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider backed by the OpenAI embeddings API.

    Kept as an optional alternative to Ollama. The `openai` package is
    imported lazily inside `__init__` so it's not a hard dependency
    when running with Ollama as the configured provider.
    """

    def __init__(self, api_key: str, model: str, batch_size: int) -> None:
        """
        Args:
            api_key: OpenAI API key.
            model: Embedding model identifier (e.g. "text-embedding-3-small").
            batch_size: Maximum number of texts sent per API call.
        """
        from openai import OpenAI  # Lazy import — optional dependency.

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._batch_size = batch_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of texts, chunked into API-sized batches."""
        from openai import OpenAIError  # Lazy import — optional dependency.

        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                response = self._client.embeddings.create(model=self._model, input=batch)
            except OpenAIError as exc:
                raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc

            embeddings.extend(item.embedding for item in response.data)
            log.debug("Embedded batch of {} text(s) via OpenAI ({})", len(batch), self._model)

        return embeddings


_PROVIDER_REGISTRY: dict[str, type[EmbeddingProvider]] = {
    "ollama": OllamaEmbeddingProvider,
    "openai": OpenAIEmbeddingProvider,
    # Additional providers are registered here as they're implemented:
    # "huggingface": HuggingFaceEmbeddingProvider,
    # "voyageai": VoyageAIEmbeddingProvider,
    # "gemini": GeminiEmbeddingProvider,
}


def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory returning the configured embedding provider.

    Reads `Settings.EMBEDDING_PROVIDER` to select the provider
    implementation and the relevant settings to configure it. No
    provider name or model is hardcoded outside of `Settings`
    defaults.

    Returns:
        An `EmbeddingProvider` instance.

    Raises:
        EmbeddingError: If `Settings.EMBEDDING_PROVIDER` names a
            provider that is not yet implemented.
    """
    settings = get_settings()
    provider_name = settings.EMBEDDING_PROVIDER.lower()

    if provider_name not in _PROVIDER_REGISTRY:
        raise EmbeddingError(
            f"Embedding provider '{provider_name}' is not implemented. "
            f"Available providers: {', '.join(_PROVIDER_REGISTRY)}."
        )

    if provider_name == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )

    if provider_name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )

    raise EmbeddingError(f"Embedding provider '{provider_name}' is registered but not wired up.")