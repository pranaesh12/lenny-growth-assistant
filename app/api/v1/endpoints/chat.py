"""
Chat API endpoint.

Exposes the chat orchestration pipeline over HTTP. Contains NO
business logic — delegates entirely to `ChatOrchestrator`.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_chat_orchestrator
from app.chat.orchestrator import ChatOrchestrator
from app.chat.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a chat message",
    description=(
        "Sends a message to the assistant. Retrieves relevant podcast "
        "knowledge, builds a grounded prompt, calls the configured LLM, "
        "and persists the exchange. Omit session_id to start a new "
        "session; responds with 404 if a provided session_id does not "
        "exist, and 502 if retrieval or generation fails upstream."
    ),
    tags=["Chat"],
)
def send_chat_message(
    payload: ChatRequest,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
) -> ChatResponse:
    """Handles a single chat turn end-to-end."""
    return orchestrator.handle_chat(payload)