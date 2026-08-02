"""
CLI script: test the chat orchestration pipeline end-to-end.

Usage:
    python scripts/test_chat.py

Creates a new session, sends a test question, and prints the
provider, model, retrieved chunks, latency, and assistant response.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.deps import _get_default_llm_manager, _get_retriever  # noqa: E402
from app.chat.exceptions import ChatOrchestrationError  # noqa: E402
from app.chat.orchestrator import ChatOrchestrator  # noqa: E402
from app.chat.schemas import ChatRequest  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.repositories.message_repository import MessageRepository  # noqa: E402
from app.repositories.session_repository import SessionRepository  # noqa: E402
from app.services.exceptions import ServiceError  # noqa: E402
from app.services.message_service import MessageService  # noqa: E402
from app.services.session_service import SessionService  # noqa: E402
from app.utils.logger import log_exception  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = SessionLocal()

    try:
        session_repository = SessionRepository(db)
        message_repository = MessageRepository(db)
        session_service = SessionService(session_repository)
        message_service = MessageService(message_repository, session_repository)

        orchestrator = ChatOrchestrator(
            session_service=session_service,
            message_service=message_service,
            message_repository=message_repository,
            retriever=_get_retriever(),
            default_llm_manager=_get_default_llm_manager(),
            settings=settings,
        )

        question = "How do I find product market fit?"
        print(f"Question: {question}\n")

        request = ChatRequest(session_id=None, message=question)

        try:
            response = orchestrator.handle_chat(request)
        except (ChatOrchestrationError, ServiceError) as exc:
            print(f"Chat request FAILED: {exc}")
            log_exception("Chat test script failed")
            sys.exit(1)

        print(f"Session ID:      {response.session_id}")
        print(f"Provider:        {response.provider}")
        print(f"Model:           {response.model}")
        print(f"Latency:         {response.latency_ms:.1f} ms")
        print(f"Token usage:     {response.token_usage.model_dump()}")
        print(f"\nRetrieved chunks ({len(response.retrieved_chunks)}):")
        for i, chunk in enumerate(response.retrieved_chunks, 1):
            print(f"  {i}. [{chunk.similarity_score:.3f}] {chunk.transcript_id} (chunk {chunk.chunk_id})")
        print(f"\nCitations ({len(response.citations)}):")
        for i, citation in enumerate(response.citations, 1):
            print(f"  {i}. {citation.title} — {citation.guest or 'unknown guest'} ({citation.youtube_url or 'no URL'})")
        print(f"\nAssistant response:\n{response.response}")

    finally:
        db.close()


if __name__ == "__main__":
    main()