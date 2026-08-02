"""
Transcript metadata API endpoints.

Exposes ONLY PostgreSQL metadata about transcripts. Transcript
chunks and embeddings live in ChromaDB and are never exposed or
integrated here. Contains NO business logic — delegates entirely to
`TranscriptService`. Repositories are never imported here.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_transcript_service
from app.schemas.transcript import TranscriptListResponse, TranscriptResponse
from app.services.transcript_service import TranscriptService

router = APIRouter()


@router.get(
    "",
    response_model=TranscriptListResponse,
    status_code=status.HTTP_200_OK,
    summary="List transcript metadata",
    description="Returns transcript metadata rows with pagination. Does not expose transcript chunks or embeddings.",
    tags=["Transcripts"],
)
def list_transcripts(
    skip: int = Query(default=0, ge=0, description="Number of rows to skip."),
    limit: int = Query(default=100, gt=0, le=500, description="Maximum number of rows to return."),
    service: TranscriptService = Depends(get_transcript_service),
) -> TranscriptListResponse:
    """Lists transcript metadata rows with pagination."""
    transcripts = service.list_transcripts(skip=skip, limit=limit)
    return TranscriptListResponse(
        transcripts=[TranscriptResponse.model_validate(t) for t in transcripts],
        count=len(transcripts),
    )


@router.get(
    "/{transcript_id}",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transcript metadata by ID",
    description="Returns a single transcript's metadata. Responds with 404 if the transcript does not exist.",
    tags=["Transcripts"],
)
def get_transcript(
    transcript_id: uuid.UUID,
    service: TranscriptService = Depends(get_transcript_service),
) -> TranscriptResponse:
    """Fetches a single transcript's metadata by ID."""
    transcript = service.get_transcript_metadata(str(transcript_id))
    return TranscriptResponse.model_validate(transcript)