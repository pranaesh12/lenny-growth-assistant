"""
Configuration service.

Contains business logic for reading and updating the application's
global runtime configuration. Uses only `ConfigurationRepository` for
data access — never touches SQLAlchemy models or query constructs
directly.
"""

from app.models.configuration import Configuration
from app.models.enums import ProviderType
from app.repositories.configuration_repository import ConfigurationRepository
from app.services.exceptions import NotFoundError, ValidationError


class ConfigurationService:
    """Business logic for global configuration management."""

    def __init__(self, repository: ConfigurationRepository) -> None:
        """
        Args:
            repository: Repository providing configuration data
                access.
        """
        self.repository = repository

    def get_configuration(self) -> Configuration:
        """
        Fetches the application's active configuration.

        Returns:
            The active `Configuration`.

        Raises:
            NotFoundError: If no configuration row exists yet (the
                application has not been initialized with a default
                configuration).
        """
        config = self.repository.get_configuration()
        if config is None:
            raise NotFoundError(
                "No configuration exists yet. The application has not been "
                "initialized with a default configuration."
            )
        return config

    def update_configuration(
        self,
        active_provider: ProviderType | None = None,
        default_model: str | None = None,
        temperature: float | None = None,
        rag_enabled: bool | None = None,
    ) -> Configuration:
        """
        Updates one or more fields of the active configuration.

        Only fields explicitly provided (non-None) are updated;
        omitted fields retain their current values.

        Args:
            active_provider: New default LLM provider, if changing.
            default_model: New default model identifier, if changing.
                Must not be blank if provided.
            temperature: New default sampling temperature, if
                changing. Must be between 0 and 1 inclusive.
            rag_enabled: New RAG-enabled flag, if changing.

        Returns:
            The updated `Configuration`.

        Raises:
            NotFoundError: If no configuration exists yet.
            ValidationError: If `active_provider` is not a valid
                `ProviderType`, `default_model` is blank, or
                `temperature` is outside the 0-1 range.
        """
        config = self.get_configuration()

        fields: dict[str, object] = {}

        if active_provider is not None:
            if not isinstance(active_provider, ProviderType):
                raise ValidationError(f"'{active_provider}' is not a valid ProviderType.")
            fields["active_provider"] = active_provider

        if default_model is not None:
            default_model = default_model.strip()
            if not default_model:
                raise ValidationError("default_model must not be blank.")
            if len(default_model) > 150:
                raise ValidationError("default_model must not exceed 150 characters.")
            fields["default_model"] = default_model

        if temperature is not None:
            if not (0.0 <= temperature <= 1.0):
                raise ValidationError("temperature must be between 0 and 1 inclusive.")
            fields["temperature"] = temperature

        if rag_enabled is not None:
            fields["rag_enabled"] = rag_enabled

        if not fields:
            # Nothing to update; return the current configuration
            # unchanged rather than issuing a no-op database write.
            return config

        updated = self.repository.update_configuration(str(config.id), **fields)
        assert updated is not None
        return updated