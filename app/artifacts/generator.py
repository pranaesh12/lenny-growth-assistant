"""
Artifact generator.

Wraps `LLMManager` to generate artifact content from a built prompt.
Does not duplicate any provider logic — all provider selection and
API calls remain in `app.llm`.
"""

import time

from app.artifacts.exceptions import ArtifactGenerationError
from app.artifacts.prompt_builder import BuiltArtifactPrompt
from app.llm.exceptions import LLMError
from app.llm.manager import LLMManager
from app.llm.schemas import LLMRequest, LLMResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["ArtifactGenerator"]


class ArtifactGenerator:
    """Generates artifact content by calling the configured LLM via `LLMManager`."""

    def generate(
        self,
        prompt: BuiltArtifactPrompt,
        llm_manager: LLMManager,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """
        Generates artifact content from a built prompt.

        Args:
            prompt: The assembled artifact prompt.
            llm_manager: The (possibly request-overridden) LLM manager to call.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            The provider-agnostic `LLMResponse`.

        Raises:
            ArtifactGenerationError: If generation fails.
        """
        request = LLMRequest(
            prompt=prompt.user_prompt,
            system_prompt=prompt.system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        log.info(
            "Artifact generation started | provider={} model={} prompt_chars={}",
            llm_manager.provider_name(),
            llm_manager.model_name(),
            len(prompt.user_prompt),
        )

        try:
            response = llm_manager.generate(request)
        except LLMError as exc:
            raise ArtifactGenerationError(f"Artifact generation failed: {exc}") from exc

        log.info(
            "Artifact generation completed | provider={} model={} latency_ms={:.1f} total_tokens={}",
            response.provider,
            response.model,
            response.latency_ms,
            response.total_tokens,
        )

        return response