"""
Artifact generation package.

Extends the chat system to generate structured, persisted artifacts
(summaries, PRDs, growth strategies, etc.) from a session's
conversation history and RAG context, via `ArtifactManager`.
"""

from app.artifacts.exceptions import (
    ArtifactError,
    ArtifactFormattingError,
    ArtifactGenerationError,
    ArtifactPromptError,
    ArtifactStorageError,
)
from app.artifacts.manager import ArtifactManager
from app.artifacts.schemas import ArtifactGenerationRequest, ArtifactGenerationResponse, ArtifactKind

__all__ = [
    "ArtifactManager",
    "ArtifactGenerationRequest",
    "ArtifactGenerationResponse",
    "ArtifactKind",
    "ArtifactError",
    "ArtifactPromptError",
    "ArtifactGenerationError",
    "ArtifactFormattingError",
    "ArtifactStorageError",
]