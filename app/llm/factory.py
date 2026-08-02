"""
LLM provider factory.

Reads Settings to determine which provider is configured and
instantiates the corresponding LLMProvider implementation. This is
the ONLY place in the application that imports concrete provider
classes directly — everything else goes through LLMManager.
"""

"""
LLM provider factory.
"""

from app.core.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.exceptions import ProviderConfigurationError
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["LLMProviderFactory"]

_SUPPORTED_PROVIDERS = {"anthropic", "openai", "ollama"}


class LLMProviderFactory:
    """Builds an LLMProvider implementation from Settings, with optional per-call overrides."""

    @staticmethod
    def create(
        settings: Settings,
        provider_override: str | None = None,
        model_override: str | None = None,
    ) -> LLMProvider:
        """
        Instantiates an LLM provider.

        Args:
            settings: The application's Settings instance.
            provider_override: If given, selects this provider instead
                of `settings.DEFAULT_PROVIDER`. Used for per-request
                provider overrides (e.g. chat orchestration).
            model_override: If given, uses this model instead of the
                provider's configured default model.

        Returns:
            A concrete `LLMProvider` implementation.

        Raises:
            ProviderConfigurationError: If the selected provider name
                is unsupported, or its required configuration is missing.
        """
        provider_name = provider_override or settings.DEFAULT_PROVIDER.value

        if provider_name not in _SUPPORTED_PROVIDERS:
            raise ProviderConfigurationError(
                f"Unsupported LLM provider '{provider_name}'. "
                f"Supported providers: {', '.join(sorted(_SUPPORTED_PROVIDERS))}."
            )

        log.info("Selecting LLM provider | provider={}", provider_name)

        if provider_name == "openai":
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=model_override or settings.OPENAI_MODEL,
                timeout=settings.LLM_TIMEOUT,
                max_retries=settings.LLM_MAX_RETRIES,
            )

        if provider_name == "anthropic":
            return AnthropicProvider(
                api_key=settings.ANTHROPIC_API_KEY,
                model=model_override or settings.ANTHROPIC_MODEL,
                timeout=settings.LLM_TIMEOUT,
                max_retries=settings.LLM_MAX_RETRIES,
            )

        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=model_override or settings.OLLAMA_MODEL,
            timeout=settings.LLM_TIMEOUT,
        )