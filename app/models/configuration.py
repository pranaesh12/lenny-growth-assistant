"""
Configuration model.

Stores the application's global runtime configuration — the single
active set of defaults controlling which LLM provider and model are
used, the default sampling temperature, and whether RAG retrieval is
enabled. This is application-wide configuration, not per-user or
per-session settings, and backs the `GET /api/v1/config` and
`PATCH /api/v1/config` endpoints (API layer implemented in a later
phase).

This model is intentionally independent: it has no foreign keys and
no relationships to any other table.
"""

import uuid

from sqlalchemy import Boolean, Float, Index, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Uuid as SQLUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ProviderType

__all__ = ["Configuration"]


class Configuration(Base, TimestampMixin):
    """
    Global application configuration.

    Represents the active runtime settings controlling default LLM
    behavior across the application: which provider and model to use
    by default, the default sampling temperature, and whether RAG
    retrieval is enabled. The application is expected to maintain a
    single active configuration row; enforcing "exactly one active
    row" (e.g. via a singleton pattern or a partial unique index) is
    a service/API-layer concern, not modeled at the schema level here.

    Numeric range validation for `temperature` (e.g. constraining it
    to 0–1) is deliberately NOT enforced at the database level — per
    the Database Design, that business validation belongs in the
    service/API layer, keeping this model a plain data container.

    Inherits `created_at` / `updated_at` from `TimestampMixin`; do
    not redefine them here.
    """

    __tablename__ = "configurations"

    __table_args__ = (
        # Speeds up lookups/filtering by the configured active provider,
        # e.g. checking which configuration rows target a given provider.
        Index("ix_configurations_active_provider", "active_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        SQLUuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key. Native UUID, generated client-side via uuid.uuid4() at insert time.",
    )

    active_provider: Mapped[ProviderType] = mapped_column(
        SQLEnum(
            ProviderType,
            name="provider_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        doc="The default LLM provider currently active (claude, openai, or ollama).",
    )

    default_model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        doc="Identifier of the default model to use with the active provider. Max 150 chars.",
    )

    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
        server_default="0.7",
        doc=(
            "Default sampling temperature applied to LLM requests. "
            "Range validation (0-1) is enforced at the service/API "
            "layer, not here."
        ),
    )

    rag_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        doc="Whether RAG (retrieval-augmented generation) is enabled by default.",
    )

    def __repr__(self) -> str:
        """Returns a concise, debug-friendly representation of the configuration."""
        return (
            f"Configuration(id={self.id!r}, active_provider={self.active_provider!r}, "
            f"default_model={self.default_model!r})"
        )