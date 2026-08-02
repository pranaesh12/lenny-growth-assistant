"""
Chat orchestrator.

Coordinates the full chat pipeline: session validation/creation,
conversation history, semantic retrieval, prompt construction, LLM
generation, and conversation persistence. This is the only module
that wires all of the above together — every dependency is injected
via the constructor.
"""

import time

from torch import chunk

from app.chat.context import load_conversation_history
from app.chat.exceptions import ChatOrchestrationError, ContextError
from app.chat.memory import save_exchange
from app.chat.prompt_builder import build_prompt
from app.chat.schemas import ChatRequest, ChatResponse, Citation, RetrievedChunkSchema, TokenUsage
from app.core.config import Settings
from app.llm.exceptions import LLMError
from app.llm.factory import LLMProviderFactory
from app.llm.manager import LLMManager
from app.llm.schemas import LLMRequest
from app.models.enums import ProviderType
from app.rag.exceptions import RAGError
from app.rag.retriever import Retriever
from app.repositories.message_repository import MessageRepository
from app.services.exceptions import NotFoundError
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["ChatOrchestrator"]


class ChatOrchestrator:
    """Coordinates session, retrieval, prompt building, LLM generation, and persistence for one chat turn."""

    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        message_repository: MessageRepository,
        retriever: Retriever,
        default_llm_manager: LLMManager,
        settings: Settings,
    ) -> None:
        """
        Args:
            session_service: Used to validate/create sessions.
            message_service: Used to persist the chat exchange.
            message_repository: Used to load conversation history.
            retriever: Used for semantic retrieval of transcript chunks.
            default_llm_manager: The default-configured LLM manager,
                used when the request does not override provider/model.
            settings: Application settings.
        """
        self._session_service = session_service
        self._message_service = message_service
        self._message_repository = message_repository
        self._retriever = retriever
        self._default_llm_manager = default_llm_manager
        self._settings = settings

    def _resolve_session_id(self, requested_session_id: str | None) -> str:
        """
        Resolves the session to use for this exchange.

        If `requested_session_id` is None, a new session is created.
        If provided, the session must already exist (server-generated
        IDs are never fabricated on the client's behalf).

        Args:
            requested_session_id: The session ID from the request, if any.

        Returns:
            The resolved session's ID.

        Raises:
            NotFoundError: If `requested_session_id` was provided but
                does not exist.
        """
        if requested_session_id is None:
            session = self._session_service.create_session()
            log.info("New session created | session_id={}", session.id)
            return session.id

        # Validates existence; raises NotFoundError if missing.
        session = self._session_service.get_session(requested_session_id)
        log.info("Continuing existing session | session_id={}", session.id)
        return session.id

    def _resolve_llm_manager(self, request: ChatRequest) -> LLMManager:
        """
        Returns the LLM manager to use for this request — the default
        manager, or a request-scoped one if `provider`/`model` were
        overridden.
        """
        if request.provider is None and request.model is None:
            return self._default_llm_manager

        provider = LLMProviderFactory.create(
            self._settings,
            provider_override=request.provider.value if request.provider else None,
            model_override=request.model,
        )
        return LLMManager(settings=self._settings, provider=provider)

    def handle_chat(self, request: ChatRequest) -> ChatResponse:
        print("=" * 60)
        print(f"HANDLE_CHAT CALLED | session={request.session_id} | message={request.message}")
        
        session_id = self._resolve_session_id(request.session_id)

        history = load_conversation_history(
            session_id=session_id,
            message_repository=self._message_repository,
            max_messages=self._settings.MAX_HISTORY_MESSAGES,
        )

        try:
            retrieved_chunks = self._retriever.retrieve(
                query=request.message, top_k=self._settings.MAX_CONTEXT_CHUNKS
            )
        except RAGError as exc:
            raise ContextError(f"Semantic retrieval failed: {exc}") from exc

        log.info("Retrieved {} chunk(s) for chat query | session_id={}", len(retrieved_chunks), session_id)

        built_prompt = build_prompt(
            system_prompt=self._settings.SYSTEM_PROMPT,
            history=history,
            retrieved_chunks=retrieved_chunks,
            user_question=request.message,
            max_context_characters=self._settings.MAX_CONTEXT_CHARACTERS,
        )
        log.info("=" * 80)
        log.info("PROMPT SENT TO LLM")
        log.info(built_prompt.user_prompt)
        log.info("=" * 80)

        llm_manager = self._resolve_llm_manager(request)
        llm_request = LLMRequest(
            prompt=built_prompt.user_prompt,
            system_prompt=built_prompt.system_prompt,
            temperature=request.temperature if request.temperature is not None else self._settings.DEFAULT_TEMPERATURE,
            max_tokens=self._settings.DEFAULT_MAX_TOKENS,
        )

        log.info(
            "Calling LLM | provider={} model={} session_id={}",
            llm_manager.provider_name(),
            llm_manager.model_name(),
            session_id,
        )
        for i, chunk in enumerate(retrieved_chunks, 1):
         log.info("=" * 80)
         log.info("Chunk {}", i)
         log.info("Title: {}", chunk.title)
         log.info("Guest: {}", chunk.guest)
         log.info("Score: {}", chunk.similarity_score)
         log.info("Text:\n{}", chunk.text)
        start_time = time.perf_counter()
        try:
            llm_response = llm_manager.generate(llm_request)
        except LLMError as exc:
            raise ChatOrchestrationError(f"LLM generation failed: {exc}") from exc
        latency_ms = (time.perf_counter() - start_time) * 1000

        log.info(
            "LLM response received | provider={} model={} latency_ms={:.1f} total_tokens={}",
            llm_response.provider,
            llm_response.model,
            latency_ms,
            llm_response.total_tokens,
        )

        save_exchange(
            session_id=session_id,
            user_content=request.message,
            assistant_content=llm_response.content,
            provider_used=ProviderType(llm_response.provider),
            message_service=self._message_service,
        )

        citations = [
            Citation(
                title=chunk.title,
                guest=chunk.guest,
                youtube_url=chunk.youtube_url,
                chunk_index=chunk.chunk_index,
            )
            for chunk in built_prompt.included_chunks
        ]
        retrieved_chunks_schema = [
            RetrievedChunkSchema(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                transcript_id=chunk.transcript_id,
                similarity_score=chunk.similarity_score,
            )
            for chunk in built_prompt.included_chunks
        ]

        return ChatResponse(
            session_id=session_id,
            response=llm_response.content,
            retrieved_chunks=retrieved_chunks_schema,
            citations=citations,
            provider=llm_response.provider,
            model=llm_response.model,
            latency_ms=llm_response.latency_ms,
            token_usage=TokenUsage(
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
            ),
        )