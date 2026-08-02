"""
CLI script: bulk-ingest all transcripts into PostgreSQL + ChromaDB.

Usage:
    python scripts/ingest_transcripts.py

Scans the configured transcripts directory, skips transcripts already
ingested (matched by deterministic transcript ID), ingests the rest,
prints progress and a final summary, and continues past individual
failures without stopping the overall run.
"""

import sys
import time
from pathlib import Path

# Allow running this script directly without the project installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.rag.embeddings import get_embedding_provider  # noqa: E402
from app.rag.ingest import ingest_transcript_file  # noqa: E402
from app.rag.loader import load_transcript_paths  # noqa: E402
from app.rag.vector_store import ChromaVectorStore  # noqa: E402
from app.repositories.transcript_repository import TranscriptRepository  # noqa: E402
from app.services.transcript_service import TranscriptService  # noqa: E402
from app.utils.logger import get_logger, log_exception  # noqa: E402

log = get_logger(__name__)


def _format_elapsed(seconds: float) -> str:
    """Formats an elapsed duration as e.g. '2m 48s'."""
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes}m {remainder}s" if minutes else f"{remainder}s"


def main() -> None:
    settings = get_settings()
    db = SessionLocal()

    ingested_count = 0
    skipped_count = 0
    failed_count = 0

    try:
        transcript_repository = TranscriptRepository(db)
        transcript_service = TranscriptService(transcript_repository)
        vector_store = ChromaVectorStore()
        embedding_provider = get_embedding_provider()

        paths = load_transcript_paths(settings.TRANSCRIPTS_DIRECTORY)
        total = len(paths)
        print(f"Transcripts discovered: {total}\n")

        run_start = time.perf_counter()

        for index, path in enumerate(paths, start=1):
            print(f"[{index}/{total}] {path.parent.name} ... ", end="", flush=True)

            try:
                _, was_skipped = ingest_transcript_file(
                    path=path,
                    transcript_repository=transcript_repository,
                    transcript_service=transcript_service,
                    vector_store=vector_store,
                    embedding_provider=embedding_provider,
                )
                if was_skipped:
                    print("skipped (already ingested)")
                    skipped_count += 1
                else:
                    print("done")
                    ingested_count += 1

            except Exception as exc:
                print(f"FAILED ({exc})")
                log_exception(f"Failed to ingest {path}", path=str(path))
                failed_count += 1
                continue

        elapsed = time.perf_counter() - run_start

        print("\n--- Ingestion Summary ---")
        print(f"Transcripts discovered: {total}")
        print(f"Successfully ingested: {ingested_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Failed: {failed_count}")
        print(f"Elapsed: {_format_elapsed(elapsed)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()