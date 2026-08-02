"""
Configuration API endpoints.

Exposes the application's single global configuration over HTTP.
Contains NO business logic — delegates entirely to
`ConfigurationService`. Repositories are never imported here.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_configuration_service
from app.schemas.configuration import ConfigurationResponse, ConfigurationUpdate
from app.services.configuration_service import ConfigurationService

router = APIRouter()


@router.get(
    "",
    response_model=ConfigurationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the active configuration",
    description="Returns the application's active global configuration. Responds with 404 if no configuration exists yet.",
    tags=["Configuration"],
)
def get_configuration(
    service: ConfigurationService = Depends(get_configuration_service),
) -> ConfigurationResponse:
    """Fetches the application's active configuration."""
    config = service.get_configuration()
    return ConfigurationResponse.model_validate(config)


@router.patch(
    "",
    response_model=ConfigurationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update the active configuration",
    description=(
        "Updates one or more fields of the application's active configuration. "
        "Only fields explicitly provided are changed. Responds with 404 if no "
        "configuration exists yet, and 422 if a provided value fails validation."
    ),
    tags=["Configuration"],
)
def update_configuration(
    payload: ConfigurationUpdate,
    service: ConfigurationService = Depends(get_configuration_service),
) -> ConfigurationResponse:
    """Updates the application's active configuration."""
    config = service.update_configuration(
        active_provider=payload.active_provider,
        default_model=payload.default_model,
        temperature=payload.temperature,
        rag_enabled=payload.rag_enabled,
    )
    return ConfigurationResponse.model_validate(config)