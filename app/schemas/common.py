"""
Shared/common Pydantic schemas used across API endpoints.

These are transport-layer response models only — NOT domain/business
models. Domain schemas (e.g. chat, users) will live in their own
modules in later phases.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "Lenny Growth Assistant",
                "version": "1.0.0",
                "environment": "local",
                "timestamp": "2025-01-01T00:00:00Z",
            }
        }
    )

    status: str = Field(..., description="Overall service status.")
    service: str = Field(..., description="Service/application name.")
    version: str = Field(..., description="Current API version.")
    environment: str = Field(..., description="Deployment environment.")
    timestamp: datetime = Field(..., description="Server UTC timestamp at response time.")


class ErrorResponse(BaseModel):
    """
    Standard error response envelope, used by global exception handlers.

    Kept here (rather than in core/exceptions.py) so any endpoint module
    can reference it as a `responses={...}` model without importing
    from the exceptions module.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "InternalServerError",
                "message": "An unexpected error occurred.",
                "request_id": "b3f1c2e4-1234-4abc-9def-abcdef123456",
            }
        }
    )

    error: str = Field(..., description="Error type/category.")
    message: str = Field(..., description="Human-readable error message.")
    request_id: str | None = Field(
        default=None, description="Correlation ID for tracing this request."
    )