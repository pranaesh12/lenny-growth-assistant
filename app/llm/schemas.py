"""
Typed request/response models for the LLM abstraction layer.

Every provider implementation accepts an `LLMRequest` and returns an
`LLMResponse`, regardless of which underlying SDK/API it wraps — this
is what makes providers interchangeable via configuration alone.
"""

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["LLMRequest", "LLMResponse"]


class LLMRequest(BaseModel):
    """A provider-agnostic request to generate a completion."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt": "What's a good way to improve onboarding?",
                "system_prompt": "You are a helpful product growth advisor.",
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": False,
            }
        }
    )

    prompt: str = Field(..., min_length=1, description="The user prompt to generate a completion for.")
    system_prompt: str | None = Field(default=None, description="Optional system/instruction prompt.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature.")
    max_tokens: int = Field(default=1024, gt=0, description="Maximum tokens to generate.")
    stream: bool = Field(default=False, description="Whether to stream the response. Not yet implemented by providers in this phase.")


class LLMResponse(BaseModel):
    """A provider-agnostic completion response, uniform across all providers."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Hello from Lenny.",
                "provider": "openai",
                "model": "gpt-4o",
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
                "finish_reason": "stop",
                "latency_ms": 842.3,
            }
        }
    )

    content: str = Field(..., description="The generated text content.")
    provider: str = Field(..., description="Name of the provider that generated this response.")
    model: str = Field(..., description="Name of the model that generated this response.")
    prompt_tokens: int | None = Field(default=None, description="Tokens consumed by the prompt, if reported by the provider.")
    completion_tokens: int | None = Field(default=None, description="Tokens generated in the completion, if reported by the provider.")
    total_tokens: int | None = Field(default=None, description="Total tokens used, if reported by the provider.")
    finish_reason: str | None = Field(default=None, description="Why generation stopped (e.g. 'stop', 'length'), if reported.")
    latency_ms: float = Field(..., description="Wall-clock time the request took, in milliseconds.")