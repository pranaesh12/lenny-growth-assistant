"""
Application entry point for the Lenny Growth Assistant backend.

This module is responsible ONLY for:
    - Instantiating the FastAPI application
    - Wiring up middleware
    - Wiring up exception handlers
    - Including the versioned API router
    - Managing application lifespan (startup/shutdown)

No business logic, database access, or LLM logic belongs here.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.logging import log_startup, log_shutdown
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.db.database import check_database_connection

settings = get_settings()

# Logging must be configured before anything else logs.
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan handler.

    Startup and shutdown hooks are placeholders in Phase 1.
    Future phases will initialize:
        - Database connection pool / engine
        - ChromaDB client
        - LangChain resources
        - Any cache / background task workers
    """
    log_startup()

    # ---------------------------------------------------------
    # Verify database connectivity during application startup.
    # The application should fail fast if PostgreSQL is
    # unavailable.
    # ---------------------------------------------------------
    if not check_database_connection():
        raise RuntimeError("Unable to establish a connection to PostgreSQL.")

    # --- Startup placeholder ---
    # e.g. app.state.db_engine = create_engine(...)
    # e.g. app.state.chroma_client = chromadb.Client(...)

    yield

    # --- Shutdown placeholder ---
    # e.g. await app.state.db_engine.dispose()
    log_shutdown()


def create_application() -> FastAPI:
    """
    Application factory.

    Encapsulating app creation in a factory function keeps the module
    import-safe for testing (e.g. multiple app instances with different
    settings/overrides in tests).
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Backend service for the Lenny Growth Assistant.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    print("BACKEND_CORS_ORIGINS =", settings.BACKEND_CORS_ORIGINS)

    application.add_middleware(LoggingMiddleware)
    application.add_middleware(RequestIDMiddleware)

    # --- Middleware (order matters: last added = outermost) ---
    application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

    

    # --- Exception handlers ---
    register_exception_handlers(application)

    # --- Routers ---
    application.include_router(api_router)

    return application


app = create_application()