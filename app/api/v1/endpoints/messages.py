"""
Message API endpoints.

Exposes message creation and retrieval over HTTP. Contains NO
business logic — delegates entirely to `MessageService`. Repositories
are never imported here.

Routes span two path shapes (nested under a session for create/list,
flat for get/delete by message ID), so this router is mounted at the
v1 router level with no fixed prefix.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_message_service
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services.message_service import MessageService

router = APIRouter()


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a message within a session",
    description="Creates a new message in the given session. Responds with 404 if the session does not exist.",
    tags=["Messages"],
)
def create_message(
    session_id: str,
    payload: MessageCreate,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """Creates a new message within a session."""
    message = service.create_message(
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        content_type=payload.content_type,
        provider_used=payload.provider_used,
        artifact_id=payload.artifact_id,
    )
    return MessageResponse.model_validate(message)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List messages in a session",
    description="Returns all messages for a session in chronological order (oldest first). Responds with 404 if the session does not exist.",
    tags=["Messages"],
)
def list_messages(
    session_id: str,
    service: MessageService = Depends(get_message_service),
) -> MessageListResponse:
    """Lists all messages for a session, in chronological order."""
    messages = service.list_messages(session_id)
    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        count=len(messages),
    )


@router.get(
    "/messages/{message_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a message by ID",
    description="Returns a single message. Responds with 404 if the message does not exist.",
    tags=["Messages"],
)
def get_message(
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """Fetches a single message by ID."""
    message = service.get_message(message_id)
    return MessageResponse.model_validate(message)


@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message",
    description="Permanently deletes a single message. Responds with 404 if the message does not exist.",
    tags=["Messages"],
)
def delete_message(
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> None:
    """Permanently deletes a message."""
    service.delete_message(message_id)