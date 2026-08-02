"""
Session API endpoints.

Exposes CRUD operations for chat sessions over HTTP. Endpoints
contain NO business logic — they validate/parse the request via
Pydantic schemas, delegate entirely to `SessionService`, and shape
the response. Repositories are never imported or referenced here.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_session_service
from app.schemas.session import (
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services.session_service import SessionService

router = APIRouter()


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
    description="Creates a new chat session with an optional title. If no title is provided, a default title is assigned.",
)
def create_session(
    payload: SessionCreate,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Creates a new session and returns it."""
    session = service.create_session(title=payload.title)
    return SessionResponse.model_validate(session)


@router.get(
    "",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List sessions",
    description="Returns active (non-archived) sessions, ordered from most recently updated to least.",
)
def list_sessions(
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """Lists active sessions, newest first."""
    sessions = service.list_sessions()
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        count=len(sessions),
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a session by ID",
    description="Returns a single session. Responds with 404 if the session does not exist.",
)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Fetches a single session by ID."""
    session = service.get_session(session_id)
    return SessionResponse.model_validate(session)


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Rename a session",
    description=(
        "Renames a session. Responds with 404 if the session does not exist, "
        "and 409 if the session is archived (archived sessions are read-only)."
    ),
)
def rename_session(
    session_id: str,
    payload: SessionUpdate,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Renames a session."""
    session = service.rename_session(session_id, payload.title)
    return SessionResponse.model_validate(session)


@router.delete(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a session (soft delete)",
    description=(
        "Archives a session rather than removing it from the database. "
        "Responds with 404 if the session does not exist, and 409 if it "
        "is already archived."
    ),
)
def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Archives (soft-deletes) a session."""
    session = service.archive_session(session_id)
    return SessionResponse.model_validate(session)