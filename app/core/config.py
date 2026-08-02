"""
Centralized application configuration.

All environment-dependent values are defined here using Pydantic v2 +
pydantic-settings. No other module should read from `os.environ`
directly — always go through the `settings` singleton exported below.

Database configuration (Phase: Supabase Migration):
    Supports two ways of configuring the database connection:
        1. A single `DATABASE_URL` (full connection string), OR
        2. Discrete Supabase fields (`SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`,
           `SUPABASE_DB_NAME`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD`),
           from which `DATABASE_URL` is assembled automatically.
    If `DATABASE_URL` is explicitly provided, it takes precedence.
    Otherwise, it is built from the discrete Supabase fields. Supabase
    PostgreSQL requires SSL for all external connections — this is
    handled in `app/db/database.py` via `connect_args`, not by
    embedding `sslmode` in the URL, so the same URL logic works
    whether pointed at Supabase or another SSL-requiring Postgres host.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import Environment, LLMProvider, LogLevel
from app.core.security import validate_secret_key


class Settings(BaseSettings):
    """
    Application settings, sourced from environment variables / `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_NAME: str = "Lenny Growth Assistant"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"

    # ------------------------------------------------------------------
    # Database (PostgreSQL via Supabase)
    # ------------------------------------------------------------------
    # Option A: a full connection string. Takes precedence if set.
    DATABASE_URL: Optional[str] = None

    # Option B: discrete Supabase fields, used to build DATABASE_URL
    # automatically if DATABASE_URL is not provided.
    SUPABASE_DB_HOST: Optional[str] = None
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_USER: Optional[str] = None
    SUPABASE_DB_PASSWORD: Optional[str] = None

    # ------------------------------------------------------------------
    # ChromaDB
    # ------------------------------------------------------------------
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION: str = "lenny_growth_knowledge"

    # ------------------------------------------------------------------
    # LLM Providers
    # ------------------------------------------------------------------
    DEFAULT_PROVIDER: LLMProvider = LLMProvider.OPENAI
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: AnyHttpUrl = "http://localhost:11434"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_DIRECTORY: str = "./logs"

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    SECRET_KEY: str = Field(..., description="Required — no insecure default.")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []


    # ------------------------------------------------------------------
    # RAG / ChromaDB
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # RAG / ChromaDB
    # ------------------------------------------------------------------
    TRANSCRIPTS_DIRECTORY: str = "./episodes"
    CHROMA_COLLECTION_NAME: str = "lenny_transcripts"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"
    RAG_CHUNK_SIZE: int =  600
    RAG_CHUNK_OVERLAP: int = 150
    RAG_TOP_K: int = 5
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_BATCH_SIZE: int = 100
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ------------------------------------------------------------------
    # LLM Provider Configuration
    # ------------------------------------------------------------------
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    OLLAMA_MODEL: str = "llama3.1"
    LLM_TIMEOUT: float = 60.0
    LLM_MAX_RETRIES: int = 3
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MAX_TOKENS: int = 1024

    # ------------------------------------------------------------------
    # Chat Orchestration
    # ------------------------------------------------------------------
    SYSTEM_PROMPT: str = """
You are the Lenny Growth Assistant.

Your ONLY knowledge source is the podcast transcript context supplied in the prompt.

Rules:

1. Always answer using the retrieved podcast transcript.
2. Never answer using your own knowledge.
3. Never recommend external websites or resources.
4. If multiple podcast episodes match, list every matching episode title.
5. When possible include:
   - Episode title
   - Guest name
   - Summary
6. If the answer is NOT present in the retrieved transcript, reply exactly:

"I couldn't find this information in the retrieved podcast transcripts."

Do not invent episode names.
Do not hallucinate.
Do not say "based on general knowledge".
"""
    MAX_HISTORY_MESSAGES: int = 10
    MAX_CONTEXT_CHUNKS: int = 5
    MAX_CONTEXT_CHARACTERS: int = 6000

    # ------------------------------------------------------------------
    # Artifact Generation
    # ------------------------------------------------------------------
    DEFAULT_ARTIFACT_PROVIDER: LLMProvider = LLMProvider.OLLAMA
    DEFAULT_ARTIFACT_MODEL: str | None = None
    DEFAULT_ARTIFACT_TEMPERATURE: float = 0.5
    MAX_ARTIFACT_CONTEXT_MESSAGES: int = 10
    MAX_ARTIFACT_CONTEXT_CHUNKS: int = 5
    MAX_ARTIFACT_OUTPUT_TOKENS: int = 1024

    # ==================================================================
    # Validators
    # ==================================================================

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: str | List[str]) -> List[str]:
        """Allow CORS origins as a comma-separated string in `.env`."""
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def reject_blank_required_secrets(cls, value: str, info) -> str:
        """Fail fast if a required secret-bearing field is blank."""
        if not value or not str(value).strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return value

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "Settings":
        """
        Ensures enough information is present to build a database
        connection, either via `DATABASE_URL` directly or via the
        full set of discrete `SUPABASE_DB_*` fields.

        Raises:
            ValueError: If neither a complete `DATABASE_URL` nor a
                complete set of Supabase fields is provided.
        """
        if self.DATABASE_URL:
            return self

        required_supabase_fields = {
            "SUPABASE_DB_HOST": self.SUPABASE_DB_HOST,
            "SUPABASE_DB_USER": self.SUPABASE_DB_USER,
            "SUPABASE_DB_PASSWORD": self.SUPABASE_DB_PASSWORD,
        }
        missing = [name for name, value in required_supabase_fields.items() if not value]
        if missing:
            raise ValueError(
                "Database is not configured: provide either DATABASE_URL, "
                f"or all of SUPABASE_DB_HOST, SUPABASE_DB_USER, "
                f"SUPABASE_DB_PASSWORD (missing: {', '.join(missing)})."
            )
        return self

    @model_validator(mode="after")
    def validate_secret_key_strength(self) -> "Settings":
        """
        Enforces production-grade SECRET_KEY strength when
        ENVIRONMENT=production. Delegates the actual rule to
        `app.core.security.validate_secret_key` so the security
        policy lives in one place.
        """
        validate_secret_key(self.SECRET_KEY, self.ENVIRONMENT)
        return self

    @model_validator(mode="after")
    def validate_default_provider_has_key(self) -> "Settings":
        """
        Warns (does not fail) if the default LLM provider has no
        API key configured. Non-fatal since no LLM calls exist yet.
        """
        provider_key_map = {
            LLMProvider.OPENAI: self.OPENAI_API_KEY,
            LLMProvider.ANTHROPIC: self.ANTHROPIC_API_KEY,
        }
        if self.DEFAULT_PROVIDER in provider_key_map and not provider_key_map[self.DEFAULT_PROVIDER]:
            import logging

            logging.getLogger(__name__).warning(
                "DEFAULT_PROVIDER is set to '%s' but its API key is not "
                "configured. LLM calls will fail once implemented.",
                self.DEFAULT_PROVIDER.value,
            )
        return self

    # ==================================================================
    # Computed properties
    # ==================================================================

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """
        Resolves the async-driver (asyncpg) database connection URL.

        If `DATABASE_URL` was explicitly supplied, it is used as-is
        (assumed to already be a valid `postgresql+asyncpg://` URL).
        Otherwise, it is assembled from the discrete `SUPABASE_DB_*`
        fields. Reserved for future async engine use — the sync
        engine currently in `app/db/database.py` uses
        `SQLALCHEMY_DATABASE_URL_SYNC` instead.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.SUPABASE_DB_USER}:{self.SUPABASE_DB_PASSWORD}"
            f"@{self.SUPABASE_DB_HOST}:{self.SUPABASE_DB_PORT}/{self.SUPABASE_DB_NAME}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URL_SYNC(self) -> str:
        """
        Resolves the sync-driver (psycopg2) database connection URL,
        used by the SQLAlchemy engine in `app/db/database.py` and by
        Alembic migrations.

        If `DATABASE_URL` was supplied and already uses a sync driver
        scheme (`postgresql://` or `postgresql+psycopg2://`), it is
        normalized to `postgresql+psycopg2://` and used as-is.
        Otherwise, the URL is assembled from the discrete
        `SUPABASE_DB_*` fields.

        Note: SSL is NOT embedded in this URL. Supabase requires SSL,
        but that requirement is enforced via SQLAlchemy `connect_args`
        in `app/db/database.py`, keeping SSL configuration explicit
        and in one place rather than string-encoded here.
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.SUPABASE_DB_USER}:{self.SUPABASE_DB_PASSWORD}"
            f"@{self.SUPABASE_DB_HOST}:{self.SUPABASE_DB_PORT}/{self.SUPABASE_DB_NAME}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def CHROMA_URL(self) -> str:
        """Assembles the ChromaDB server URL from host/port."""
        return f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"

    @computed_field  # type: ignore[misc]
    @property
    def AVAILABLE_LLM_PROVIDERS(self) -> List[str]:
        """
        Returns the list of LLM providers that currently have the
        credentials needed to be usable. Ollama is always considered
        available since it requires no API key.
        """
        available = [LLMProvider.OLLAMA.value]
        if self.OPENAI_API_KEY:
            available.append(LLMProvider.OPENAI.value)
        if self.ANTHROPIC_API_KEY:
            available.append(LLMProvider.ANTHROPIC.value)
        return available

    @computed_field  # type: ignore[misc]
    @property
    def IS_PRODUCTION(self) -> bool:
        """Convenience flag for environment-gated logic elsewhere."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @computed_field  # type: ignore[misc]
    @property
    def IS_DEVELOPMENT(self) -> bool:
        """Convenience flag for environment-gated logic elsewhere."""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @computed_field  # type: ignore[misc]
    @property
    def IS_TESTING(self) -> bool:
        """Convenience flag for environment-gated logic elsewhere."""
        return self.ENVIRONMENT == Environment.TESTING


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached `Settings` instance (singleton for the process).
    """
    return Settings()


settings = get_settings()