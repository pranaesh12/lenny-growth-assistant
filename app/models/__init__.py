"""
Models package.

Re-exports the declarative `Base`, shared mixins, domain enums, and
ORM model classes so the rest of the codebase can import consistently
from a single location:

    from app.models import Base, TimestampMixin
    from app.models import MessageRole, ProviderType, ArtifactType
    from app.models import Session, Message, Artifact, Transcript, Configuration

Each model module is imported and re-exported here. Importing
`app.models` anywhere in the application — including from Alembic's
`env.py` — is sufficient to register all defined models on
`Base.metadata`, which Alembic's autogenerate relies on for schema
discovery.

Phase 6.8 resolution: `Artifact.id` was retyped from UUID to the
project's prefixed string-ID convention (`art_<hex>`), matching
`Session.id` / `Message.id`, resolving the foreign-key type mismatch
against `Message.artifact_id` (String). The schema is now internally
consistent and ready for the first production migration.
"""

from app.models.artifact import Artifact, generate_artifact_id
from app.models.base import Base, TimestampMixin
from app.models.configuration import Configuration
from app.models.enums import (
    ArtifactType,
    ChatMode,
    MessageRole,
    ProviderType,
    RenderFormat,
)
from app.models.message import Message, generate_message_id
from app.models.session import Session, generate_session_id
from app.models.transcript import Transcript

__all__ = [
    "Base",
    "TimestampMixin",
    "MessageRole",
    "ProviderType",
    "ArtifactType",
    "RenderFormat",
    "ChatMode",
    "Session",
    "generate_session_id",
    "Message",
    "generate_message_id",
    "Artifact",
    "generate_artifact_id",
    "Transcript",
    "Configuration",
]