"""
Global exception handlers.

Registers application-wide exception handlers so all error responses
share a consistent JSON shape (`ErrorResponse`), regardless of where
in the app an exception originates.

Phase 9 scope: in addition to the generic/framework-level exceptions
handled since Phase 1 (HTTPException, RequestValidationError,
unhandled Exception), this module now also handles the service-layer
exceptions introduced in Phase 8 (`app/services/exceptions.py`):
NotFoundError -> 404, ConflictError -> 409, and ValidationError (the
service-layer one, distinct from Pydantic's RequestValidationError)
-> 422. This lets API routes simply call a service and let business-
rule violations propagate as exceptions, with no try/except logic
duplicated in every endpoint.
"""

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse
from app.services.exceptions import ConflictError, NotFoundError
from app.services.exceptions import ValidationError as ServiceValidationError
from app.chat.exceptions import ChatOrchestrationError
from app.artifacts.exceptions import ArtifactError

logger = logging.getLogger("app.exceptions")


def _get_request_id(request: Request) -> str:
    """Retrieves the correlation ID set by RequestIDMiddleware, if present."""
    return getattr(request.state, "request_id", str(uuid.uuid4()))


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handles FastAPI/Starlette HTTPException (e.g. 404, 403, custom raises)."""
    request_id = _get_request_id(request)
    logger.warning(
        "HTTPException: status=%s detail=%s request_id=%s",
        exc.status_code,
        exc.detail,
        request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTPException",
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump(),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handles Pydantic/FastAPI request validation errors (422)."""
    request_id = _get_request_id(request)
    logger.warning(
        "ValidationError: errors=%s request_id=%s",
        exc.errors(),
        request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request validation failed.",
            request_id=request_id,
        ).model_dump(),
    )


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Handles service-layer NotFoundError (e.g. session/message/artifact not found) -> 404."""
    request_id = _get_request_id(request)
    logger.warning(
        "NotFoundError: %s request_id=%s",
        str(exc),
        request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            error="NotFoundError",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )


async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Handles service-layer ConflictError (e.g. renaming an archived session) -> 409."""
    request_id = _get_request_id(request)
    logger.warning(
        "ConflictError: %s request_id=%s",
        str(exc),
        request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=ErrorResponse(
            error="ConflictError",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )


async def service_validation_error_handler(
    request: Request, exc: ServiceValidationError
) -> JSONResponse:
    """Handles service-layer ValidationError (business-rule violations) -> 422."""
    request_id = _get_request_id(request)
    logger.warning(
        "ValidationError: %s request_id=%s",
        str(exc),
        request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for any unhandled exception.

    Prevents raw stack traces / internal details from leaking to
    clients. Full exception is logged server-side with traceback.
    """
    request_id = _get_request_id(request)
    logger.exception(
        "Unhandled exception: request_id=%s error=%s",
        request_id,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred. Please try again later.",
            request_id=request_id,
        ).model_dump(),
    )
async def chat_orchestration_error_handler(request: Request, exc: ChatOrchestrationError) -> JSONResponse:
    """Handles chat orchestration failures (retrieval, prompt building, LLM calls, persistence) -> 502."""
    request_id = _get_request_id(request)
    logger.error("ChatOrchestrationError: %s request_id=%s", str(exc), request_id)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error="ChatOrchestrationError",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )
async def artifact_error_handler(request: Request, exc: ArtifactError) -> JSONResponse:
    """Handles artifact generation pipeline failures -> 502."""
    request_id = _get_request_id(request)
    logger.error("ArtifactError: %s request_id=%s", str(exc), request_id)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error="ArtifactError",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all global exception handlers on the FastAPI app instance.

    Called once from `create_application()` in `app/main.py`.
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    app.add_exception_handler(ConflictError, conflict_error_handler)
    app.add_exception_handler(ServiceValidationError, service_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(ChatOrchestrationError, chat_orchestration_error_handler)
    app.add_exception_handler(ArtifactError, artifact_error_handler)