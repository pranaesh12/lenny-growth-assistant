"""
Abstract base class for LLM providers.

Every concrete provider (OpenAI, Anthropic, Ollama) implements this
interface, so calling code never needs to know which provider is
actually active — only that it satisfies this contract.
"""

from abc import ABC, abstractmethod

from app.llm.schemas import LLMRequest, LLMResponse

__all__ = ["LLMProvider"]


class LLMProvider(ABC):
    """Abstract interface every LLM provider implementation must satisfy."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generates a completion for the given request.

        Args:
            request: The provider-agnostic generation request.

        Returns:
            A provider-agnostic `LLMResponse`.

        Raises:
            AuthenticationError: If credentials are invalid/missing.
            RateLimitError: If the provider rate-limits the request.
            ProviderUnavailableError: If the provider cannot be reached.
            GenerationError: If generation otherwise fails.
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verifies the provider is reachable, authenticated, and the
        configured model is accessible.

        Returns:
            True if the provider is healthy.

        Raises:
            ProviderUnavailableError: If the provider cannot be reached.
            AuthenticationError: If credentials are invalid.
            ProviderConfigurationError: If the configured model is
                inaccessible/not found.
        """
        raise NotImplementedError

    @abstractmethod
    def provider_name(self) -> str:
        """Returns this provider's name (e.g. "openai", "claude", "ollama")."""
        raise NotImplementedError

    @abstractmethod
    def model_name(self) -> str:
        """Returns the model name this provider instance is configured to use."""
        raise NotImplementedError