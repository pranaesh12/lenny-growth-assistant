"""
Version 1 API router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import artifacts, configuration, health, messages, sessions, transcripts
from app.core.config import get_settings
from app.api.v1.endpoints import artifacts, chat, configuration, health, messages, sessions, transcripts

settings = get_settings()

api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)

api_v1_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_v1_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["Sessions"],
)

# messages.py and artifacts.py declare their own full paths internally
# (mixing /sessions/{session_id}/... and flat /messages, /artifacts
# paths), so they are included with no additional prefix here.
api_v1_router.include_router(messages.router)
api_v1_router.include_router(artifacts.router)

api_v1_router.include_router(
    transcripts.router,
    prefix="/transcripts",
    tags=["Transcripts"],
)

api_v1_router.include_router(
    configuration.router,
    prefix="/configuration",
    tags=["Configuration"],
)

api_v1_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)