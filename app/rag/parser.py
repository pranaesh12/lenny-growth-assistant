"""
Transcript markdown parser.

Extracts YAML frontmatter metadata and the transcript body from a
single transcript file's raw text, and computes a deterministic
transcript ID. Contains no filesystem-scanning or database logic —
pure parsing.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from app.rag.exceptions import TranscriptParseError
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["TranscriptDocument", "parse_transcript_file", "compute_transcript_id"]

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Fixed namespace for deterministic uuid5 generation. Using a fixed,
# arbitrary namespace UUID (rather than NAMESPACE_URL/NAMESPACE_DNS)
# ensures IDs are stable and reproducible specifically for this
# project's transcript archive, independent of any change to the
# input string's format.
_TRANSCRIPT_ID_NAMESPACE = uuid.UUID("7c3a1e4a-9b1e-4f0a-9c2d-2f6b1e8a5d31")


@dataclass
class TranscriptDocument:
    """Structured result of parsing one transcript file."""

    transcript_id: uuid.UUID
    title: str
    guest: str | None
    youtube_url: str | None
    publish_date: date | None
    description: str | None
    transcript_text: str


def compute_transcript_id(
    video_id: str | None,
    youtube_url: str | None,
    fallback_key: str,
) -> uuid.UUID:
    """
    Computes a deterministic transcript ID.

    Preference order: `video_id` (most stable, unique per YouTube
    video), then `youtube_url`, then `fallback_key` (typically the
    file's absolute path) if neither is available. The same input
    always produces the same UUID, guaranteeing duplicate detection
    across multiple ingestion runs — no random UUIDs are ever
    generated.

    Args:
        video_id: The transcript's YouTube video ID, if present.
        youtube_url: The transcript's YouTube URL, if present.
        fallback_key: A guaranteed-available string (e.g. the file's
            absolute path) used only if both of the above are missing.

    Returns:
        A deterministic `uuid.UUID`.
    """
    if video_id:
        return uuid.uuid5(_TRANSCRIPT_ID_NAMESPACE, video_id)
    if youtube_url:
        return uuid.uuid5(_TRANSCRIPT_ID_NAMESPACE, youtube_url)
    return uuid.uuid5(_TRANSCRIPT_ID_NAMESPACE, fallback_key)


def _parse_publish_date(raw_value: object) -> date | None:
    """Normalizes a frontmatter publish_date value into a `date`, if possible."""
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return datetime.strptime(raw_value.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_transcript_file(path: Path) -> TranscriptDocument:
    """
    Parses a single transcript file into structured metadata plus the
    transcript body.

    Args:
        path: Path to the transcript file.

    Returns:
        A `TranscriptDocument` with extracted metadata, body text,
        and a deterministic `transcript_id`.

    Raises:
        TranscriptParseError: If the file is unreadable, has no valid
            YAML frontmatter block, or the frontmatter is malformed.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TranscriptParseError(f"Could not read file {path}: {exc}") from exc

    match = _FRONTMATTER_PATTERN.match(raw_text)
    if not match:
        raise TranscriptParseError(f"No valid YAML frontmatter found in {path}")

    frontmatter_raw, body = match.groups()

    try:
        metadata = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        raise TranscriptParseError(f"Malformed YAML frontmatter in {path}: {exc}") from exc

    if not isinstance(metadata, dict):
        raise TranscriptParseError(f"Frontmatter in {path} did not parse to a mapping.")

    title = metadata.get("title") or path.parent.name
    guest = metadata.get("guest")
    youtube_url = metadata.get("youtube_url")
    video_id = metadata.get("video_id")
    description = metadata.get("description")
    publish_date = _parse_publish_date(metadata.get("publish_date"))

    transcript_id = compute_transcript_id(
        video_id=video_id,
        youtube_url=youtube_url,
        fallback_key=str(path.resolve()),
    )

    transcript_text = body.strip()
    if not transcript_text:
        raise TranscriptParseError(f"Transcript body is empty in {path}")

    log.debug("Parsed transcript '{}' (id={}) from {}", title, transcript_id, path)

    return TranscriptDocument(
        transcript_id=transcript_id,
        title=title,
        guest=guest,
        youtube_url=youtube_url,
        publish_date=publish_date,
        description=description,
        transcript_text=transcript_text,
    )