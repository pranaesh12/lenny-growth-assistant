"""
OpenAI provider implementation.
"""

import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError as OpenAIAuthenticationError,
    OpenAI,
    RateLimitError as OpenAIRateLimitError,
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

__all__ = ["OpenAIProvider"]


class OpenAIProvider(LLMProvider):
    """LLM provider backed by the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str, timeout: float, max_retries: int) -> None:
        """
        Args:
            api_key: OpenAI API key.
            model: Model identifier (e.g. "gpt-4o").
            timeout: Per-request timeout, in seconds.
            max_retries: Maximum automatic retries the SDK performs
                for transient failures (timeouts, connection errors,
                429s) before raising.

        Raises:
            ProviderConfigurationError: If `api_key` is blank.
        """
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")

        self._model = model
        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def provider_name(self) -> str:
        """Returns "openai"."""
        return "openai"

    def model_name(self) -> str:
        """Returns the configured OpenAI model name."""
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generates a completion via the OpenAI Chat Completions API."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        log.info(
            "OpenAI request started | model={} max_tokens={} temperature={}",
            self._model,
            request.max_tokens,
            request.temperature,
        )
        start_time = time.perf_counter()

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except OpenAIAuthenticationError as exc:
            raise AuthenticationError(f"OpenAI authentication failed: {exc}") from exc
        except OpenAIRateLimitError as exc:
            raise RateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise ProviderUnavailableError(f"OpenAI unreachable: {exc}") from exc
        except APIStatusError as exc:
            raise GenerationError(f"OpenAI request failed (status {exc.status_code}): {exc}") from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        choice = completion.choices[0]
        content = choice.message.content or ""
        usage = completion.usage

        log.info(
            "OpenAI request completed | model={} latency_ms={:.1f} total_tokens={}",
            self._model,
            latency_ms,
            usage.total_tokens if usage else None,
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name(),
            model=self._model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            finish_reason=choice.finish_reason,
            latency_ms=latency_ms,
        )

    def health_check(self) -> bool:
        """
        Verifies the OpenAI provider is reachable, authenticated, and
        the configured model is accessible, by listing available models
        and confirming the configured model is among them.

        Returns:
            True if healthy.

        Raises:
            AuthenticationError: If credentials are invalid.
            ProviderUnavailableError: If OpenAI cannot be reached.
            ProviderConfigurationError: If the configured model is not
                available to this account.
        """
        try:
            models = self._client.models.list()
        except OpenAIAuthenticationError as exc:
            raise AuthenticationError(f"OpenAI authentication failed: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise ProviderUnavailableError(f"OpenAI unreachable: {exc}") from exc
        except APIStatusError as exc:
            raise ProviderUnavailableError(f"OpenAI health check failed (status {exc.status_code}): {exc}") from exc

        available_ids = {m.id for m in models.data}
        if self._model not in available_ids:
            raise ProviderConfigurationError(
                f"Configured OpenAI model '{self._model}' is not available to this account."
            )

        log.info("OpenAI health check passed | model={}", self._model)
        return True