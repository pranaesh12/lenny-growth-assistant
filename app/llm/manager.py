"""
LLM manager.

The single entry point the rest of the application uses to generate
completions. Wraps the factory-selected provider and applies retry
logic for transient failures. No other module should import a
concrete provider class or the factory directly — only `LLMManager`.
"""

import time

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.exceptions import (
    AuthenticationError,
    GenerationError,
    LLMError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.llm.factory import LLMProviderFactory
from app.llm.schemas import LLMRequest, LLMResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["LLMManager"]

# Exceptions considered transient and worth retrying. Authentication,
# configuration, and generation errors are NOT retried, since retrying
# an invalid API key or malformed request cannot succeed.
_RETRYABLE_EXCEPTIONS = (ProviderUnavailableError, RateLimitError)


class LLMManager:
    """Unified interface for generating LLM completions, provider-agnostic."""

    def __init__(self, settings: Settings | None = None, provider: LLMProvider | None = None) -> None:
        """
        Args:
            settings: Application settings. Defaults to `get_settings()`.
            provider: An explicit provider instance to use, bypassing
                the factory. Primarily for testing; production code
                should omit this and let the factory select based on
                `settings.DEFAULT_PROVIDER`.
        """
        self._settings = settings or get_settings()
        self._provider = provider or LLMProviderFactory.create(self._settings)

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generates a completion using the configured provider, retrying
        transient failures up to `Settings.LLM_MAX_RETRIES` times with
        exponential backoff.

        Args:
            request: The provider-agnostic generation request.

        Returns:
            A provider-agnostic `LLMResponse`.

        Raises:
            AuthenticationError: If credentials are invalid. Not retried.
            ProviderConfigurationError: If misconfigured. Not retried.
            GenerationError: If generation fails for a non-transient
                reason. Not retried.
            ProviderUnavailableError: If the provider remains
                unreachable after all retries are exhausted.
            RateLimitError: If the provider remains rate-limited after
                all retries are exhausted.
        """
        max_retries = self._settings.LLM_MAX_RETRIES
        last_exception: LLMError | None = None

        for attempt in range(1, max_retries + 2):  # +1 initial attempt, +1 for range inclusivity
            try:
                return self._provider.generate(request)
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                if attempt > max_retries:
                    break
                backoff_seconds = 2 ** (attempt - 1)
                log.warning(
                    "LLM request failed (attempt {}/{}), retrying in {}s | provider={} error={}",
                    attempt,
                    max_retries + 1,
                    backoff_seconds,
                    self._provider.provider_name(),
                    str(exc),
                )
                time.sleep(backoff_seconds)
            except (AuthenticationError, ProviderConfigurationError, GenerationError):
                # Not retryable — propagate immediately.
                raise

        log.error(
            "LLM request failed after {} attempt(s) | provider={}",
            max_retries + 1,
            self._provider.provider_name(),
        )
        assert last_exception is not None
        raise last_exception

    def health_check(self) -> bool:
        """
        Runs the configured provider's health check.

        Returns:
            True if the provider is healthy.

        Raises:
            Whatever exception the underlying provider's
            `health_check()` raises (not retried — a health check is
            meant to reflect current state, not be masked by retries).
        """
        return self._provider.health_check()

    def provider_name(self) -> str:
        """Returns the active provider's name."""
        return self._provider.provider_name()

    def model_name(self) -> str:
        """Returns the active provider's configured model name."""
        return self._provider.model_name()