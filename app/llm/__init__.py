"""
LLM abstraction layer.

Provides a unified interface (`LLMManager`) for generating completions
across multiple providers (OpenAI, Anthropic/Claude, Ollama), selected
entirely via `Settings.DEFAULT_PROVIDER` — no code changes are needed
to switch providers.

Scope: provider abstraction, selection, and unified request/response
handling only. No RAG retrieval, prompt construction, chat
orchestration, or conversation memory exists here — those are later
phases.
"""

from app.llm.exceptions import (
    AuthenticationError,
    GenerationError,
    LLMError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.llm.manager import LLMManager
from app.llm.schemas import LLMRequest, LLMResponse

__all__ = [
    "LLMManager",
    "LLMRequest",
    "LLMResponse",
    "LLMError",
    "ProviderConfigurationError",
    "ProviderUnavailableError",
    "AuthenticationError",
    "RateLimitError",
    "GenerationError",
]