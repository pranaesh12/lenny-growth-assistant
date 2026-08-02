"""
Transcript file loader.

Recursively discovers transcript files under the configured episodes
directory. Contains no parsing or database logic — purely a
filesystem scan.
"""

import os
from pathlib import Path

from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["load_transcript_paths"]

_TRANSCRIPT_FILENAME = "transcript.md"


def load_transcript_paths(root_directory: str) -> list[Path]:
    """
    Recursively finds all transcript files under a directory.

    Only files named exactly `transcript.md` are treated as
    transcripts — other markdown files (e.g. README.md) are ignored.
    Hidden directories (starting with a dot) are skipped entirely,
    so tooling folders like `.git` are never scanned.

    Args:
        root_directory: Root directory to scan (e.g. "./episodes").

    Returns:
        A sorted list of transcript file paths, for deterministic
        processing order across runs.

    Raises:
        FileNotFoundError: If `root_directory` does not exist.
    """
    root = Path(root_directory)
    if not root.exists():
        raise FileNotFoundError(f"Transcripts directory not found: {root_directory}")

    discovered: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune hidden directories in-place so os.walk does not
        # descend into them on the next iteration.
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        if _TRANSCRIPT_FILENAME in filenames:
            discovered.append(Path(dirpath) / _TRANSCRIPT_FILENAME)

    discovered.sort()
    log.info("Discovered {} transcript file(s) under {}", len(discovered), root_directory)
    return discovered