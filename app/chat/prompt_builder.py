"""
Prompt builder.

Assembles the final prompt from conversation history, retrieved
transcript chunks, and the current user question. Performs NO LLM
calls — pure text assembly.
"""

from dataclasses import dataclass

from app.chat.exceptions import PromptBuildError
from app.models.enums import MessageRole
from app.models.message import Message
from app.rag.retriever import RetrievedChunk
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["BuiltPrompt", "build_prompt"]


@dataclass
class BuiltPrompt:
    """The assembled prompt, ready to pass to an LLM provider."""

    system_prompt: str
    user_prompt: str
    included_chunks: list[RetrievedChunk]


def _format_history(history: list[Message]) -> str:
    """Formats prior messages as a readable transcript block."""
    if not history:
        return "(no prior messages in this session)"
    lines = []
    for message in history:
        speaker = "User" if message.role == MessageRole.USER else "Assistant"
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


def _select_chunks_within_budget(
    chunks: list[RetrievedChunk], max_characters: int
) -> list[RetrievedChunk]:
    """
    Selects retrieved chunks, in relevance order, up to a character
    budget. Stops adding chunks once the next one would exceed the
    budget, rather than truncating a chunk mid-text — so every
    included chunk remains complete and citable.
    """
    selected: list[RetrievedChunk] = []
    running_total = 0
    for chunk in chunks:
        if running_total + len(chunk.text) > max_characters:
            break
        selected.append(chunk)
        running_total += len(chunk.text)
    return selected


def _format_knowledge(chunks: list[RetrievedChunk]) -> str:
    """Formats selected transcript chunks as a readable knowledge block."""
    if not chunks:
        return "(no relevant podcast knowledge found)"
    blocks = []
    for chunk in chunks:
        guest_line = f" — Guest: {chunk.guest}" if chunk.guest else ""
        blocks.append(f"[{chunk.title}{guest_line}]\n{chunk.text}")
    return "\n\n".join(blocks)


def build_prompt(
    system_prompt: str,
    history: list[Message],
    retrieved_chunks: list[RetrievedChunk],
    user_question: str,
    max_context_characters: int,
) -> BuiltPrompt:
    """
    Builds the final prompt from conversation history, retrieved
    transcript chunks, and the current question.

    Args:
        system_prompt: The base system prompt (from Settings).
        history: Prior messages in the session, chronological order.
        retrieved_chunks: Candidate transcript chunks, in relevance
            order (most relevant first).
        user_question: The current user message.
        max_context_characters: Maximum total characters of retrieved
            chunk text to include in the prompt.

    Returns:
        A `BuiltPrompt` with the system prompt, assembled user-facing
        prompt (history + knowledge + question), and the list of
        chunks actually included (for citation purposes).

    Raises:
        PromptBuildError: If prompt assembly fails.
    """
    try:
        included_chunks = _select_chunks_within_budget(retrieved_chunks, max_context_characters)

        user_prompt = f"""
You MUST answer ONLY from the podcast transcript below.

=========================
CONVERSATION HISTORY
=========================
{_format_history(history)}

=========================
PODCAST TRANSCRIPTS
=========================
{_format_knowledge(included_chunks)}

=========================
USER QUESTION
=========================
{user_question}

Instructions:

- Answer ONLY using the podcast transcript.
- If multiple episodes match, list all of them.
- Mention episode title and guest.
- Summarize the relevant discussion.
- If the transcript does not contain the answer, say:
"I couldn't find this information in the retrieved podcast transcripts."
"""
    except Exception as exc:
        raise PromptBuildError(f"Failed to build prompt: {exc}") from exc

    log.debug(
        "Prompt built | history_messages={} chunks_included={}/{} prompt_chars={}",
        len(history),
        len(included_chunks),
        len(retrieved_chunks),
        len(user_prompt),
    )

    return BuiltPrompt(system_prompt=system_prompt, user_prompt=user_prompt, included_chunks=included_chunks)