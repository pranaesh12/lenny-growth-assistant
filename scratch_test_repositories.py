"""
Scratch test script for the Repository Layer (Phase 7).

NOT part of the permanent codebase — this is a one-off manual
verification script to confirm the repositories work correctly
against the real Supabase database. Run it once, read the output,
then delete it. It creates and deletes real rows in your database.

Usage:
    python scratch_test_repositories.py
"""

from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.enums import ArtifactType, MessageRole, ProviderType, RenderFormat
from app.repositories import (
    ArtifactRepository,
    ConfigurationRepository,
    MessageRepository,
    SessionRepository,
    TranscriptRepository,
)


def main() -> None:
    db = SessionLocal()

    try:
        # --- SessionRepository ---
        session_repo = SessionRepository(db)
        session = session_repo.create(title="Scratch Test Session")
        print(f"Created session: {session.id} | title={session.title!r}")

        fetched = session_repo.get_session(session.id)
        assert fetched is not None, "get_session() failed to find the created session"
        print(f"Fetched session: {fetched.id}")

        session_repo.update_title(session.id, "Renamed Scratch Session")
        session_repo.archive_session(session.id)
        archived_check = session_repo.get_session(session.id)
        print(f"After update+archive: title={archived_check.title!r}, archived={archived_check.archived}")

        session_repo.restore_session(session.id)
        recent = session_repo.get_recent_sessions(limit=5)
        print(f"Recent sessions count: {len(recent)}")

        # --- MessageRepository ---
        message_repo = MessageRepository(db)
        user_msg = message_repo.create_message(
            session_id=session.id,
            role=MessageRole.USER,
            content="Hello, this is a test message.",
        )
        print(f"Created user message: {user_msg.id}")

        assistant_msg = message_repo.create_message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="Hello! This is a test response.",
            provider_used=ProviderType.OPENAI,
        )
        print(f"Created assistant message: {assistant_msg.id}")

        messages = message_repo.get_messages_for_session(session.id)
        print(f"Messages in session: {len(messages)} (expected 2)")
        assert len(messages) == 2, "Expected exactly 2 messages"

        # --- ArtifactRepository ---
        artifact_repo = ArtifactRepository(db)
        artifact = artifact_repo.create_artifact(
            session_id=session.id,
            title="Scratch Test Essay",
            type=ArtifactType.ESSAY,
            render_format=RenderFormat.MARKDOWN,
            content="# Test Essay\n\nThis is scratch test content.",
        )
        print(f"Created artifact: {artifact.id}")

        artifacts = artifact_repo.get_session_artifacts(session.id)
        print(f"Artifacts in session: {len(artifacts)} (expected 1)")
        assert len(artifacts) == 1, "Expected exactly 1 artifact"

        # Link the assistant message to the artifact and confirm it persists.
        message_repo.update(assistant_msg.id, artifact_id=artifact.id)
        linked = message_repo.get_by_id(assistant_msg.id)
        print(f"Assistant message artifact_id: {linked.artifact_id} (expected {artifact.id})")
        assert linked.artifact_id == artifact.id

        # --- TranscriptRepository ---
        transcript_repo = TranscriptRepository(db)
        transcript = transcript_repo.create_transcript_metadata(
            title="Scratch Test Transcript",
            ingested_at=datetime.now(timezone.utc),
            source_url="https://example.com/scratch-test-transcript",
            chunk_count=5,
        )
        print(f"Created transcript: {transcript.id}")

        fetched_transcript = transcript_repo.get_by_source_url(
            "https://example.com/scratch-test-transcript"
        )
        assert fetched_transcript is not None, "get_by_source_url() failed"
        print(f"Fetched transcript by source_url: {fetched_transcript.id}")

        # --- ConfigurationRepository ---
        config_repo = ConfigurationRepository(db)
        config = config_repo.create(
            active_provider=ProviderType.OPENAI,
            default_model="gpt-4o",
        )
        print(f"Created configuration: {config.id}")

        active_config = config_repo.get_configuration()
        assert active_config is not None, "get_configuration() failed"
        print(f"Active configuration: {active_config.id}, provider={active_config.active_provider}")

        config_repo.update_configuration(config.id, temperature=0.9)
        updated_config = config_repo.get_by_id(config.id)
        print(f"Updated configuration temperature: {updated_config.temperature} (expected 0.9)")
        assert updated_config.temperature == 0.9

        print("\nAll repository operations succeeded.")

        # --- Cleanup ---
        print("\nCleaning up test data...")
        message_repo.delete_messages_for_session(session.id)
        artifact_repo.delete(artifact.id)
        session_repo.delete(session.id)  # also cascades any remaining messages/artifacts
        transcript_repo.delete(transcript.id)
        config_repo.delete(config.id)
        print("Cleanup complete.")

    except Exception:
        db.rollback()
        print("\nA test step failed — rolled back. See traceback below.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()