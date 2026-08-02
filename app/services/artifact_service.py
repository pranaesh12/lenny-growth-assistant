"""
Artifact service.

Contains business logic for creating and querying artifacts within a
session. Uses `ArtifactRepository` for artifact data access and
`SessionRepository` to validate that a parent session exists before
creating an artifact — never touches SQLAlchemy models or query
constructs directly.
"""

from app.models.artifact import Artifact
from app.models.enums import ArtifactType, RenderFormat
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.session_repository import SessionRepository
from app.services.exceptions import NotFoundError, ValidationError


class ArtifactService:
    """Business logic for artifact management."""

    def __init__(
        self,
        repository: ArtifactRepository,
        session_repository: SessionRepository,
    ) -> None:
        """
        Args:
            repository: Repository providing artifact data access.
            session_repository: Repository used to validate that a
                parent session exists before creating an artifact.
        """
        self.repository = repository
        self.session_repository = session_repository

    def create_artifact(
        self,
        session_id: str,
        title: str,
        type: ArtifactType,
        render_format: RenderFormat,
        content: str,
        kind: str | None = None,
    ) -> Artifact:
        """
        Creates a new artifact within a session.

        Args:
            session_id: The parent session's primary key.
            title: Human-readable artifact title. Must not be blank.
            type: The kind of content this artifact represents.
            render_format: The markup format the content should be
                rendered as.
            content: The full artifact content. Must not be blank.
            kind: Optional precise artifact template identifier
                (e.g. "prd"), distinct from the structural `type`.

        Returns:
            The newly created `Artifact`.

        Raises:
            NotFoundError: If the parent session does not exist.
            ValidationError: If `title`/`content` are blank, `title`
                exceeds 200 characters, or `type`/`render_format` are
                not valid enum members.
        """
        if self.session_repository.get_session(session_id) is None:
            raise NotFoundError(f"Cannot create an artifact: session '{session_id}' was not found.")

        title = title.strip()
        if not title:
            raise ValidationError("Artifact title must not be blank.")
        if len(title) > 200:
            raise ValidationError("Artifact title must not exceed 200 characters.")

        if not content or not content.strip():
            raise ValidationError("Artifact content must not be blank.")

        if not isinstance(type, ArtifactType):
            raise ValidationError(f"'{type}' is not a valid ArtifactType.")

        if not isinstance(render_format, RenderFormat):
            raise ValidationError(f"'{render_format}' is not a valid RenderFormat.")

        return self.repository.create_artifact(
            session_id=session_id,
            title=title,
            type=type,
            render_format=render_format,
            content=content,
            kind=kind,
        )
    def get_artifact(self, artifact_id: str) -> Artifact:
        """
        Fetches a single artifact by ID.

        Args:
            artifact_id: The artifact's primary key.

        Returns:
            The matching `Artifact`.

        Raises:
            NotFoundError: If no artifact exists with that ID.
        """
        artifact = self.repository.get_by_id(artifact_id)
        if artifact is None:
            raise NotFoundError(f"Artifact '{artifact_id}' was not found.")
        return artifact

    def list_session_artifacts(self, session_id: str) -> list[Artifact]:
        """
        Lists all artifacts belonging to a session.

        Args:
            session_id: The parent session's primary key.

        Returns:
            A list of `Artifact` rows, most recently edited first.

        Raises:
            NotFoundError: If the session does not exist.
        """
        if self.session_repository.get_session(session_id) is None:
            raise NotFoundError(f"Session '{session_id}' was not found.")
        return self.repository.get_session_artifacts(session_id)

    def delete_artifact(self, artifact_id: str) -> None:
        """
        Permanently deletes an artifact. Any message referencing it
        has its `artifact_id` set to NULL automatically (database-
        level `ON DELETE SET NULL`).

        Args:
            artifact_id: The artifact's primary key.

        Raises:
            NotFoundError: If no artifact exists with that ID.
        """
        self.get_artifact(artifact_id)
        self.repository.delete(artifact_id)