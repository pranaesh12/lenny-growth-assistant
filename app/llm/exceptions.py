"""
LLM provider exceptions.

Unified exception hierarchy that every provider implementation maps
its own SDK/HTTP errors into, so calling code (LLMManager and, in a
later phase, chat orchestration) only ever needs to handle these
exceptions — never provider-specific ones.
"""


class LLMError(Exception):
    """Base class for all LLM provider errors."""


class ProviderConfigurationError(LLMError):
    """Raised when a provider is misconfigured (missing/invalid settings) before any request is made."""


class ProviderUnavailableError(LLMError):
    """Raised when a provider cannot be reached (network failure, server down, timeout)."""


class AuthenticationError(LLMError):
    """Raised when a provider rejects the request due to invalid/missing credentials."""


class RateLimitError(LLMError):
    """Raised when a provider reports the request was rate-limited (HTTP 429 or equivalent)."""


class GenerationError(LLMError):
    """Raised when a provider accepts the request but fails to generate a valid response."""


__all__ = [
    "LLMError",
    "ProviderConfigurationError",
    "ProviderUnavailableError",
    "AuthenticationError",
    "RateLimitError",
    "GenerationError",
]