"""
Artifact content formatter.

Normalizes raw LLM output into a consistent format before persistence.
Default output format is Markdown. JSON is a future-ready format slot,
not yet implemented (no artifact template currently requests it).
"""

from app.artifacts.exceptions import ArtifactFormattingError
from app.models.enums import RenderFormat
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["format_content"]


def format_content(raw_content: str, render_format: RenderFormat) -> str:
    """
    Normalizes raw LLM output for consistent storage/display.

    Args:
        raw_content: The unprocessed text returned by the LLM.
        render_format: The target render format.

    Returns:
        The normalized content string.

    Raises:
        ArtifactFormattingError: If formatting fails, or an
            unsupported render format is requested.
    """
    try:
        content = raw_content.strip()

        if render_format == RenderFormat.MARKDOWN:
            # Strip a leading ```markdown / ``` fence some models wrap
            # output in, despite being instructed not to.
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
            return content

        if render_format == RenderFormat.HTML:
            # No artifact template currently targets HTML output;
            # pass through unchanged if one ever does.
            return content

        raise ArtifactFormattingError(f"Unsupported render format: {render_format}")

    except ArtifactFormattingError:
        raise
    except Exception as exc:
        raise ArtifactFormattingError(f"Failed to format artifact content: {exc}") from exc