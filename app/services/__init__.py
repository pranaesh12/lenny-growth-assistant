"""
Services package.

Re-exports all service classes and the shared service-layer
exceptions so the rest of the codebase (API layer, in a later phase)
can import consistently from a single location:

    from app.services import SessionService, NotFoundError

Services contain business logic only. They never construct
SQLAlchemy queries or reference model classes for query purposes —
all data access goes through the repository layer, injected via each
service's constructor. Services have no knowledge of FastAPI,
HTTP requests, or Pydantic schemas.
"""

from app.services.artifact_service import ArtifactService
from app.services.configuration_service import ConfigurationService
from app.services.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.services.transcript_service import TranscriptService

__all__ = [
    "SessionService",
    "MessageService",
    "ArtifactService",
    "TranscriptService",
    "ConfigurationService",
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
]