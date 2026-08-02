"""
Health check endpoint.

Provides a lightweight liveness/readiness probe for the application.
Intentionally has NO dependencies on the database, ChromaDB, or any
external service in Phase 1 — it only confirms the API process itself
is up and responding. Deeper dependency checks (DB connectivity,
vector store reachability, etc.) will be added in later phases once
those integrations exist.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns basic service health/status information.",
)
async def health_check() -> HealthResponse:
    """
    Simple health check endpoint.

    Returns:
        HealthResponse: current service status, name, version, and
        server timestamp (UTC).
    """
    logger.debug("Health check requested")
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )