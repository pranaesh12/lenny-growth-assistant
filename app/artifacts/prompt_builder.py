"""
Artifact prompt builder.

Assembles the prompt for artifact generation from conversation
history, retrieved transcript chunks, the selected artifact
template, and optional user instructions. Performs NO LLM calls.
"""

from dataclasses import dataclass

from app.artifacts.exceptions import ArtifactPromptError
from app.artifacts.schemas import ArtifactTemplate
from app.models.enums import MessageRole
from app.models.message import Message
from app.rag.retriever import RetrievedChunk
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["BuiltArtifactPrompt", "build_artifact_prompt"]


@dataclass
class BuiltArtifactPrompt:
    """The assembled artifact generation prompt, ready to pass to an LLM provider."""

    system_prompt: str
    user_prompt: str
    included_chunks: list[RetrievedChunk]


def _format_history(history: list[Message]) -> str:
    """Formats prior messages as a readable transcript block."""
    if not history:
        return "(no prior conversation in this session)"
    lines = []
    for message in history:
        speaker = "User" if message.role == MessageRole.USER else "Assistant"
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


def _format_knowledge(chunks: list[RetrievedChunk]) -> str:
    """Formats retrieved transcript chunks as a readable knowledge block."""
    if not chunks:
        return "(no relevant podcast knowledge found)"
    blocks = []
    for chunk in chunks:
        guest_line = f" — Guest: {chunk.guest}" if chunk.guest else ""
        blocks.append(f"[{chunk.title}{guest_line}]\n{chunk.text}")
    return "\n\n".join(blocks)


def build_artifact_prompt(
    template: ArtifactTemplate,
    history: list[Message],
    retrieved_chunks: list[RetrievedChunk],
    user_instructions: str | None,
) -> BuiltArtifactPrompt:
    """
    Builds the final artifact generation prompt.

    Args:
        template: The selected artifact template (instructions, DB type).
        history: Prior messages in the session, chronological order.
        retrieved_chunks: Retrieved transcript chunks to ground the artifact in.
        user_instructions: Optional additional instructions from the user.

    Returns:
        A `BuiltArtifactPrompt` ready to pass to `ArtifactGenerator`.

    Raises:
        ArtifactPromptError: If prompt assembly fails.
    """
    try:
        system_prompt = (
            "You are an expert writing assistant. Generate the requested "
            "document using the conversation history and podcast knowledge "
            "provided as grounding context. Output clean, well-structured "
            "Markdown only — no commentary about the task itself."
        )

        output_requirements = (
            "Output only the finished document in Markdown. Do not include "
            "preamble, meta-commentary, or a restatement of these instructions."
        )

        instructions_block = template.instructions
        if user_instructions:
            instructions_block += f"\n\nAdditional instructions: {user_instructions}"

        user_prompt = (
            f"## Conversation History\n{_format_history(history)}\n\n"
            f"## Relevant Podcast Context\n{_format_knowledge(retrieved_chunks)}\n\n"
            f"## Artifact Instructions\n{instructions_block}\n\n"
            f"## Output Requirements\n{output_requirements}"
        )
    except Exception as exc:
        raise ArtifactPromptError(f"Failed to build artifact prompt: {exc}") from exc

    log.debug(
        "Artifact prompt built | history_messages={} chunks={} prompt_chars={}",
        len(history),
        len(retrieved_chunks),
        len(user_prompt),
    )

    return BuiltArtifactPrompt(system_prompt=system_prompt, user_prompt=user_prompt, included_chunks=retrieved_chunks)