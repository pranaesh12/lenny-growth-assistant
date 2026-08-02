"""
CLI script: test the artifact generation pipeline end-to-end.

Usage:
    python scripts/test_artifact_generation.py

Creates a session, sends a question, generates an artifact from the
resulting conversation, saves it, retrieves it back, and prints the
result.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.deps import _get_default_artifact_llm_manager, _get_retriever  # noqa: E402
from app.artifacts.exceptions import ArtifactError  # noqa: E402
from app.artifacts.generator import ArtifactGenerator  # noqa: E402
from app.artifacts.manager import ArtifactManager  # noqa: E402
from app.artifacts.schemas import ArtifactGenerationRequest, ArtifactKind  # noqa: E402
from app.chat.orchestrator import ChatOrchestrator  # noqa: E402
from app.chat.schemas import ChatRequest  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.repositories.artifact_repository import ArtifactRepository  # noqa: E402
from app.repositories.message_repository import MessageRepository  # noqa: E402
from app.repositories.session_repository import SessionRepository  # noqa: E402
from app.services.artifact_service import ArtifactService  # noqa: E402
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
        artifact_repository = ArtifactRepository(db)
        session_service = SessionService(session_repository)
        message_service = MessageService(message_repository, session_repository)
        artifact_service = ArtifactService(artifact_repository, session_repository)

        retriever = _get_retriever()

        # Step 1: create a session and ask a question via chat, so
        # there's real conversation history to generate an artifact from.
        chat_orchestrator = ChatOrchestrator(
            session_service=session_service,
            message_service=message_service,
            message_repository=message_repository,
            retriever=retriever,
            default_llm_manager=_get_default_artifact_llm_manager(),
            settings=settings,
        )
        print("Asking a question to build conversation history...")
        chat_response = chat_orchestrator.handle_chat(
            ChatRequest(session_id=None, message="How do I find product market fit?")
        )
        print(f"Session ID: {chat_response.session_id}\n")

        # Step 2: generate an artifact from that session.
        artifact_manager = ArtifactManager(
            session_service=session_service,
            artifact_service=artifact_service,
            message_repository=message_repository,
            retriever=retriever,
            default_artifact_llm_manager=_get_default_artifact_llm_manager(),
            generator=ArtifactGenerator(),
            settings=settings,
        )

        print("Generating artifact (growth_strategy)...")
        try:
            result = artifact_manager.generate_artifact(
                ArtifactGenerationRequest(
                    session_id=chat_response.session_id,
                    artifact_type=ArtifactKind.GROWTH_STRATEGY,
                )
            )
        except (ArtifactError, ServiceError) as exc:
            print(f"Artifact generation FAILED: {exc}")
            log_exception("Artifact generation test failed")
            sys.exit(1)

        # Step 3: retrieve it back via the repository, confirming persistence.
        stored = artifact_repository.get_by_id(result.artifact_id)

        print("\n--- Result ---")
        print(f"Artifact ID:  {result.artifact_id}")
        print(f"Artifact Type: {result.artifact_type.value}")
        print(f"Provider:     {result.provider}")
        print(f"Model:        {result.model}")
        print(f"Latency:      {result.latency_ms:.1f} ms")
        print(f"Retrieved OK: {stored is not None}")
        print(f"\nContent preview:\n{result.content[:400]}...")

    finally:
        db.close()


if __name__ == "__main__":
    main()