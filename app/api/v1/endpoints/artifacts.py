"""
Artifact API endpoints.

Exposes artifact creation and retrieval over HTTP. Contains NO
business logic — delegates entirely to `ArtifactService`.
Repositories are never imported here.

Routes span two path shapes (flat for create/get/delete, nested
under a session for listing), so this router is mounted at the v1
router level with no fixed prefix.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_artifact_service
from app.schemas.artifact import ArtifactCreate, ArtifactListResponse, ArtifactResponse
from app.services.artifact_service import ArtifactService
from app.api.deps import get_artifact_manager
from app.artifacts.manager import ArtifactManager
from app.artifacts.schemas import ArtifactGenerationRequest, ArtifactGenerationResponse

router = APIRouter()


@router.post(
    "/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an artifact",
    description="Creates a new artifact within a session. Responds with 404 if the session does not exist.",
    tags=["Artifacts"],
)
def create_artifact(
    payload: ArtifactCreate,
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactResponse:
    """Creates a new artifact within a session."""
    artifact = service.create_artifact(
        session_id=payload.session_id,
        title=payload.title,
        type=payload.type,
        render_format=payload.render_format,
        content=payload.content,
    )
    return ArtifactResponse.model_validate(artifact)


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an artifact by ID",
    description="Returns a single artifact. Responds with 404 if the artifact does not exist.",
    tags=["Artifacts"],
)
def get_artifact(
    artifact_id: str,
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactResponse:
    """Fetches a single artifact by ID."""
    artifact = service.get_artifact(artifact_id)
    return ArtifactResponse.model_validate(artifact)


@router.get(
    "/sessions/{session_id}/artifacts",
    response_model=ArtifactListResponse,
    status_code=status.HTTP_200_OK,
    summary="List artifacts in a session",
    description="Returns all artifacts for a session, most recently updated first. Responds with 404 if the session does not exist.",
    tags=["Artifacts"],
)
def list_session_artifacts(
    session_id: str,
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactListResponse:
    """Lists all artifacts for a session."""
    artifacts = service.list_session_artifacts(session_id)
    return ArtifactListResponse(
        artifacts=[ArtifactResponse.model_validate(a) for a in artifacts],
        count=len(artifacts),
    )


@router.delete(
    "/artifacts/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an artifact",
    description=(
        "Permanently deletes an artifact. Any message referencing it has "
        "its artifact reference cleared automatically. Responds with 404 "
        "if the artifact does not exist."
    ),
    tags=["Artifacts"],
)
def delete_artifact(
    artifact_id: str,
    service: ArtifactService = Depends(get_artifact_service),
) -> None:
    """Permanently deletes an artifact."""
    service.delete_artifact(artifact_id)


@router.post(
    "/artifacts/generate",
    response_model=ArtifactGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an artifact from a session's conversation",
    description=(
        "Generates a structured artifact (summary, PRD, growth strategy, etc.) "
        "using the session's conversation history and relevant podcast context, "
        "then persists it. Responds with 404 if the session does not exist, "
        "and 502 if generation fails upstream."
    ),
    tags=["Artifacts"],
)


def generate_artifact(
    payload: ArtifactGenerationRequest,
    manager: ArtifactManager = Depends(get_artifact_manager),
) -> ArtifactGenerationResponse:
    """Generates and persists an artifact from a session's conversation."""
    return manager.generate_artifact(payload)






















