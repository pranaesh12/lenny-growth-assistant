"""
Anthropic (Claude) provider implementation.

Note on naming: this project's Settings.DEFAULT_PROVIDER uses the
value "claude" (established in earlier phases, matching the
ProviderType enum already migrated into the PostgreSQL schema).
This class is named AnthropicProvider per the SDK/vendor it wraps,
but is selected via the config value "claude" — see
app/llm/factory.py.
"""

import time

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError as AnthropicAuthenticationError,
    RateLimitError as AnthropicRateLimitError,
)

from app.llm.base import LLMProvider
from app.llm.exceptions import (
    AuthenticationError,
    GenerationError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.llm.schemas import LLMRequest, LLMResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["AnthropicProvider"]


class AnthropicProvider(LLMProvider):
    """LLM provider backed by the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str, timeout: float, max_retries: int) -> None:
        """
        Args:
            api_key: Anthropic API key.
            model: Model identifier (e.g. "claude-sonnet-4-5").
            timeout: Per-request timeout, in seconds.
            max_retries: Maximum automatic retries the SDK performs
                for transient failures.

        Raises:
            ProviderConfigurationError: If `api_key` is blank.
        """
        if not api_key:
            raise ProviderConfigurationError("ANTHROPIC_API_KEY is not configured.")

        self._model = model
        self._client = Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def provider_name(self) -> str:
        """Returns "claude" (see module docstring for naming rationale)."""
        return "claude"

    def model_name(self) -> str:
        """Returns the configured Anthropic model name."""
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generates a completion via the Anthropic Messages API."""
        log.info(
            "Anthropic request started | model={} max_tokens={} temperature={}",
            self._model,
            request.max_tokens,
            request.temperature,
        )
        start_time = time.perf_counter()

        try:
            message = self._client.messages.create(
                model=self._model,
                system=request.system_prompt or "",
                messages=[{"role": "user", "content": request.prompt}],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except AnthropicAuthenticationError as exc:
            raise AuthenticationError(f"Anthropic authentication failed: {exc}") from exc
        except AnthropicRateLimitError as exc:
            raise RateLimitError(f"Anthropic rate limit exceeded: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise ProviderUnavailableError(f"Anthropic unreachable: {exc}") from exc
        except APIStatusError as exc:
            raise GenerationError(f"Anthropic request failed (status {exc.status_code}): {exc}") from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        content = "".join(block.text for block in message.content if hasattr(block, "text"))

        log.info(
            "Anthropic request completed | model={} latency_ms={:.1f} total_tokens={}",
            self._model,
            latency_ms,
            message.usage.input_tokens + message.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name(),
            model=self._model,
            prompt_tokens=message.usage.input_tokens,
            completion_tokens=message.usage.output_tokens,
            total_tokens=message.usage.input_tokens + message.usage.output_tokens,
            finish_reason=message.stop_reason,
            latency_ms=latency_ms,
        )

    def health_check(self) -> bool:
        """
        Verifies the Anthropic provider is reachable and authenticated
        by sending a minimal 1-token request.

        Anthropic's API has no lightweight "list models" endpoint
        equivalent to OpenAI's, so a minimal real request is the most
        reliable way to confirm reachability, authentication, and
        model accessibility together.

        Returns:
            True if healthy.

        Raises:
            AuthenticationError: If credentials are invalid.
            ProviderUnavailableError: If Anthropic cannot be reached.
            ProviderConfigurationError: If the configured model is
                invalid/inaccessible.
        """
        try:
            self._client.messages.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        except AnthropicAuthenticationError as exc:
            raise AuthenticationError(f"Anthropic authentication failed: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise ProviderUnavailableError(f"Anthropic unreachable: {exc}") from exc
        except APIStatusError as exc:
            if exc.status_code == 404:
                raise ProviderConfigurationError(
                    f"Configured Anthropic model '{self._model}' was not found."
                ) from exc
            raise ProviderUnavailableError(f"Anthropic health check failed (status {exc.status_code}): {exc}") from exc

        log.info("Anthropic health check passed | model={}", self._model)
        return True