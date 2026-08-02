"""
Artifact generation exceptions.
"""


class ArtifactError(Exception):
    """Base class for all artifact generation errors."""


class ArtifactPromptError(ArtifactError):
    """Raised when the artifact prompt cannot be assembled."""


class ArtifactGenerationError(ArtifactError):
    """Raised when LLM generation of an artifact fails."""


class ArtifactFormattingError(ArtifactError):
    """Raised when the generated content cannot be formatted/normalized."""


class ArtifactStorageError(ArtifactError):
    """Raised when the artifact cannot be persisted."""


__all__ = [
    "ArtifactError",
    "ArtifactPromptError",
    "ArtifactGenerationError",
    "ArtifactFormattingError",
    "ArtifactStorageError",
]