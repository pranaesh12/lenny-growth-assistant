"""
Repositories package.

Re-exports the base repository and all model-specific repositories
so the rest of the codebase (service layer, in a later phase) can
import consistently from a single location:

    from app.repositories import SessionRepository, MessageRepository

Repositories are pure data-access classes: they perform SQLAlchemy
CRUD operations only. They never contain business logic, never call
an LLM provider, and never know anything about FastAPI requests,
responses, or dependency injection beyond accepting a `Session`
object in their constructor.
"""

from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.base import BaseRepository
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.transcript_repository import TranscriptRepository

__all__ = [
    "BaseRepository",
    "SessionRepository",
    "MessageRepository",
    "ArtifactRepository",
    "TranscriptRepository",
    "ConfigurationRepository",
]