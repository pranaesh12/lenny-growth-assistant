"""
Shared FastAPI dependencies.

Provides dependency-injectable factories for services, so endpoint
modules never construct repositories or services manually and never
import repositories directly — only services, wired here.
"""

from typing import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session as ORMSession

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.artifact_service import ArtifactService
from app.services.configuration_service import ConfigurationService
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.services.transcript_service import TranscriptService
from functools import lru_cache

from app.chat.orchestrator import ChatOrchestrator
from app.llm.manager import LLMManager
from app.rag.retriever import Retriever
from app.artifacts.generator import ArtifactGenerator
from app.artifacts.manager import ArtifactManager
from app.llm.factory import LLMProviderFactory


__all__ = [
    "get_settings",
    "Settings",
    "get_session_service",
    "get_message_service",
    "get_artifact_service",
    "get_transcript_service",
    "get_configuration_service",
    "get_chat_orchestrator",
    "get_artifact_manager",
]


def get_session_service(db: ORMSession = Depends(get_db)) -> Iterator[SessionService]:
    """Provides a `SessionService` wired to a request-scoped `SessionRepository`."""
    repository = SessionRepository(db)
    yield SessionService(repository)


def get_message_service(db: ORMSession = Depends(get_db)) -> Iterator[MessageService]:
    """
    Provides a `MessageService` wired to request-scoped `MessageRepository`
    and `SessionRepository` instances (the latter used to validate that a
    parent session exists before creating a message).
    """
    message_repository = MessageRepository(db)
    session_repository = SessionRepository(db)
    yield MessageService(message_repository, session_repository)


def get_artifact_service(db: ORMSession = Depends(get_db)) -> Iterator[ArtifactService]:
    """
    Provides an `ArtifactService` wired to request-scoped
    `ArtifactRepository` and `SessionRepository` instances.
    """
    artifact_repository = ArtifactRepository(db)
    session_repository = SessionRepository(db)
    yield ArtifactService(artifact_repository, session_repository)


def get_transcript_service(db: ORMSession = Depends(get_db)) -> Iterator[TranscriptService]:
    """Provides a `TranscriptService` wired to a request-scoped `TranscriptRepository`."""
    repository = TranscriptRepository(db)
    yield TranscriptService(repository)


def get_configuration_service(db: ORMSession = Depends(get_db)) -> Iterator[ConfigurationService]:
    """Provides a `ConfigurationService` wired to a request-scoped `ConfigurationRepository`."""
    repository = ConfigurationRepository(db)
    yield ConfigurationService(repository)

@lru_cache
def _get_retriever() -> Retriever:
    """Process-wide cached Retriever — reuses one Chroma client/embedding provider across requests."""
    return Retriever()


@lru_cache
def _get_default_llm_manager() -> LLMManager:
    """Process-wide cached default LLMManager, built from Settings.DEFAULT_PROVIDER."""
    return LLMManager()

@lru_cache
def _get_default_artifact_llm_manager() -> LLMManager:
    """Process-wide cached default LLMManager for artifact generation, built from Settings.DEFAULT_ARTIFACT_PROVIDER."""
    settings = get_settings()
    provider = LLMProviderFactory.create(
        settings,
        provider_override=settings.DEFAULT_ARTIFACT_PROVIDER.value,
        model_override=settings.DEFAULT_ARTIFACT_MODEL,
    )
    return LLMManager(settings=settings, provider=provider)


def get_chat_orchestrator(db: ORMSession = Depends(get_db)) -> Iterator[ChatOrchestrator]:
    """Provides a `ChatOrchestrator` wired to request-scoped repositories/services and cached retriever/LLM manager."""
    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)
    session_service = SessionService(session_repository)
    message_service = MessageService(message_repository, session_repository)
    yield ChatOrchestrator(
        session_service=session_service,
        message_service=message_service,
        message_repository=message_repository,
        retriever=_get_retriever(),
        default_llm_manager=_get_default_llm_manager(),
        settings=get_settings(),
    )

def get_artifact_manager(db: ORMSession = Depends(get_db)) -> Iterator[ArtifactManager]:
    """Provides an `ArtifactManager` wired to request-scoped repositories/services and cached retriever/LLM manager."""
    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)
    artifact_repository = ArtifactRepository(db)
    session_service = SessionService(session_repository)
    artifact_service = ArtifactService(artifact_repository, session_repository)
    yield ArtifactManager(
        session_service=session_service,
        artifact_service=artifact_service,
        message_repository=message_repository,
        retriever=_get_retriever(),
        default_artifact_llm_manager=_get_default_artifact_llm_manager(),
        generator=ArtifactGenerator(),
        settings=get_settings(),
    )


























   

