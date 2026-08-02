"""
Pydantic schemas for the Configuration API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProviderType

__all__ = ["ConfigurationUpdate", "ConfigurationResponse"]


class ConfigurationUpdate(BaseModel):
    """
    Request body for updating the application's global configuration.

    All fields are optional; only fields explicitly provided are
    updated, and omitted fields retain their current values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "active_provider": "openai",
                "default_model": "gpt-4o",
                "temperature": 0.8,
                "rag_enabled": True,
            }
        }
    )

    active_provider: ProviderType | None = Field(default=None, description="Default LLM provider to activate.")
    default_model: str | None = Field(default=None, min_length=1, max_length=150, description="Default model identifier.")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Default sampling temperature (0-1).")
    rag_enabled: bool | None = Field(default=None, description="Whether RAG retrieval is enabled by default.")


class ConfigurationResponse(BaseModel):
    """Response body representing the application's global configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Configuration row identifier (UUID).")
    active_provider: ProviderType = Field(..., description="Currently active default LLM provider.")
    default_model: str = Field(..., description="Currently active default model identifier.")
    temperature: float = Field(..., description="Currently active default sampling temperature.")
    rag_enabled: bool = Field(..., description="Whether RAG retrieval is currently enabled by default.")
    created_at: datetime = Field(..., description="UTC timestamp of configuration creation.")
    updated_at: datetime = Field(..., description="UTC timestamp of the last modification.")