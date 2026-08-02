"""
Artifact manager.

Coordinates the full artifact generation pipeline: session
validation, conversation history, semantic retrieval, prompt
construction, LLM generation, formatting, and persistence. This is
the only module that wires all of the above together for artifact
generation.
"""

from app.artifacts.exceptions import ArtifactStorageError
from app.artifacts.formatter import format_content
from app.artifacts.generator import ArtifactGenerator
from app.artifacts.prompt_builder import build_artifact_prompt
from app.artifacts.schemas import ARTIFACT_TEMPLATES, ArtifactGenerationRequest, ArtifactGenerationResponse
from app.chat.context import load_conversation_history
from app.chat.schemas import TokenUsage
from app.core.config import Settings
from app.llm.factory import LLMProviderFactory
from app.llm.manager import LLMManager
from app.models.enums import RenderFormat
from app.rag.exceptions import RAGError
from app.rag.retriever import Retriever
from app.repositories.message_repository import MessageRepository
from app.services.artifact_service import ArtifactService
from app.services.exceptions import ServiceError
from app.services.session_service import SessionService
from app.utils.logger import get_logger

log = get_logger(__name__)

__all__ = ["ArtifactManager"]


class ArtifactManager:
    """Coordinates session validation, retrieval, prompt building, generation, and persistence for artifacts."""

    def __init__(
        self,
        session_service: SessionService,
        artifact_service: ArtifactService,
        message_repository: MessageRepository,
        retriever: Retriever,
        default_artifact_llm_manager: LLMManager,
        generator: ArtifactGenerator,
        settings: Settings,
    ) -> None:
        """
        Args:
            session_service: Used to validate the target session exists.
            artifact_service: Used to persist the generated artifact.
            message_repository: Used to load conversation history.
            retriever: Used for semantic retrieval of transcript chunks.
            default_artifact_llm_manager: The default-configured LLM
                manager for artifact generation, used when the request
                does not override provider/model.
            generator: Wraps the LLM call.
            settings: Application settings.
        """
        self._session_service = session_service
        self._artifact_service = artifact_service
        self._message_repository = message_repository
        self._retriever = retriever
        self._default_artifact_llm_manager = default_artifact_llm_manager
        self._generator = generator
        self._settings = settings

    def _resolve_llm_manager(self, request: ArtifactGenerationRequest) -> LLMManager:
        """Returns the default artifact LLM manager, or a request-scoped override."""
        if request.provider is None and request.model is None:
            return self._default_artifact_llm_manager

        provider = LLMProviderFactory.create(
            self._settings,
            provider_override=request.provider.value if request.provider else None,
            model_override=request.model,
        )
        return LLMManager(settings=self._settings, provider=provider)

    def generate_artifact(self, request: ArtifactGenerationRequest) -> ArtifactGenerationResponse:
        """
        Executes the full artifact generation pipeline.

        Args:
            request: The artifact generation request.

        Returns:
            An `ArtifactGenerationResponse` with the generated artifact.

        Raises:
            NotFoundError: If `request.session_id` does not exist.
            HistoryError: If conversation history fails to load.
            ArtifactPromptError: If prompt assembly fails.
            ArtifactGenerationError: If LLM generation fails.
            ArtifactFormattingError: If content formatting fails.
            ArtifactStorageError: If persistence fails.
        """
        # Validates existence; raises NotFoundError if missing.
        session = self._session_service.get_session(request.session_id)
        log.info("Artifact requested | session_id={} artifact_type={}", session.id, request.artifact_type.value)

        template = ARTIFACT_TEMPLATES[request.artifact_type]

        history = load_conversation_history(
            session_id=session.id,
            message_repository=self._message_repository,
            max_messages=self._settings.MAX_ARTIFACT_CONTEXT_MESSAGES,
        )

        try:
            retrieved_chunks = self._retriever.retrieve(
                query=request.instructions or template.default_title,
                top_k=self._settings.MAX_ARTIFACT_CONTEXT_CHUNKS,
            )
        except RAGError as exc:
            log.warning("Artifact retrieval failed, proceeding without podcast context | error={}", str(exc))
            retrieved_chunks = []

        built_prompt = build_artifact_prompt(
            template=template,
            history=history,
            retrieved_chunks=retrieved_chunks,
            user_instructions=request.instructions,
        )

        llm_manager = self._resolve_llm_manager(request)
        llm_response = self._generator.generate(
            prompt=built_prompt,
            llm_manager=llm_manager,
            temperature=(
                request.temperature if request.temperature is not None else self._settings.DEFAULT_ARTIFACT_TEMPERATURE
            ),
            max_tokens=self._settings.MAX_ARTIFACT_OUTPUT_TOKENS,
        )

        formatted_content = format_content(llm_response.content, RenderFormat.MARKDOWN)

        title = request.title or template.default_title

        try:
            artifact = self._artifact_service.create_artifact(
                session_id=session.id,
                title=title,
                type=template.db_type,
                render_format=RenderFormat.MARKDOWN,
                content=formatted_content,
                kind=request.artifact_type.value,
            )
        except ServiceError as exc:
            raise ArtifactStorageError(f"Failed to persist artifact: {exc}") from exc

        log.info("Artifact saved | artifact_id={} session_id={} kind={}", artifact.id, session.id, request.artifact_type.value)

        return ArtifactGenerationResponse(
            artifact_id=artifact.id,
            session_id=session.id,
            artifact_type=request.artifact_type,
            title=artifact.title,
            content=artifact.content,
            provider=llm_response.provider,
            model=llm_response.model,
            created_at=artifact.created_at,
            latency_ms=llm_response.latency_ms,
            token_usage=TokenUsage(
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
            ),
        )