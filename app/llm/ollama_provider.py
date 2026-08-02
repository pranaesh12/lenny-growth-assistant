"""
Ollama provider implementation.

Uses Ollama's HTTP API directly via httpx, rather than a dedicated
Ollama Python SDK, keeping the dependency surface small and
consistent with how this project's RAG embedding layer (Phase 11)
already talks to Ollama.
"""

import time

import httpx

from app.llm.base import LLMProvider
from app.llm.exceptions import (
    GenerationError,
    ProviderConfigurationError,
    ProviderUnavailableError,
)
from app.llm.schemas import LLMRequest, LLMResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["OllamaProvider"]


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama server's HTTP API."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        """
        Args:
            base_url: Base URL of the running Ollama server
                (e.g. "http://localhost:11434").
            model: Model name pulled into Ollama (e.g. "llama3.1").
            timeout: Request timeout, in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def provider_name(self) -> str:
        """Returns "ollama"."""
        return "ollama"

    def model_name(self) -> str:
        """Returns the configured Ollama model name."""
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generates a completion via Ollama's `/api/generate` endpoint."""
        log.info(
            "Ollama request started | model={} max_tokens={} temperature={}",
            self._model,
            request.max_tokens,
            request.temperature,
        )
        start_time = time.perf_counter()

        payload = {
            "model": self._model,
            "prompt": request.prompt,
            "system": request.system_prompt or "",
            "stream": False,
            "think": False,  # Skip internal reasoning tokens for thinking-capable models (e.g. Qwen3), so max_tokens is spent entirely on the visible answer.
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Ollama request timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Could not connect to Ollama at {self._base_url}: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ProviderConfigurationError(
                    f"Ollama model '{self._model}' is not installed. "
                    f"Run: ollama pull {self._model}"
                ) from exc
            raise GenerationError(
                f"Ollama request failed (status {exc.response.status_code}): {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        body = response.json()
        # Prefer "response" (the final answer). Fall back to "thinking"
        # only if "response" is empty and the model put everything
        # there instead (e.g. "think" unsupported by this model/tag,
        # or the request was cut off mid-reasoning).
        content = body.get("response") or body.get("thinking") or ""
        prompt_tokens = body.get("prompt_eval_count")
        completion_tokens = body.get("eval_count")
        total_tokens = (
            prompt_tokens + completion_tokens
            if prompt_tokens is not None and completion_tokens is not None
            else None
        )

        log.info(
            "Ollama request completed | model={} latency_ms={:.1f} total_tokens={}",
            self._model,
            latency_ms,
            total_tokens,
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name(),
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason="stop" if body.get("done") else None,
            latency_ms=latency_ms,
        )

    def health_check(self) -> bool:
        """
        Verifies the Ollama server is reachable and the configured
        model is installed, via Ollama's `/api/tags` endpoint.

        Returns:
            True if healthy.

        Raises:
            ProviderUnavailableError: If the Ollama server cannot be
                reached.
            ProviderConfigurationError: If the configured model is
                not installed.
        """
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=self._timeout)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Ollama health check timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Could not connect to Ollama at {self._base_url}: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailableError(
                f"Ollama health check failed (status {exc.response.status_code}): {exc}"
            ) from exc

        installed_models = {m["name"] for m in response.json().get("models", [])}
        # Ollama model names may include a ":tag" suffix (e.g. "llama3.1:latest");
        # match on the base name if an exact match isn't found.
        base_names = {name.split(":")[0] for name in installed_models}
        if self._model not in installed_models and self._model not in base_names:
            raise ProviderConfigurationError(
                f"Ollama model '{self._model}' is not installed. "
                f"Run: ollama pull {self._model}"
            )

        log.info("Ollama health check passed | model={}", self._model)
        return True