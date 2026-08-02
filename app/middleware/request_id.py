"""
Request ID middleware.

Assigns a unique correlation ID to every incoming request, making it
available to:
    - Downstream logging (via `LoggingMiddleware` / log records)
    - Response headers (for client-side tracing)
    - Exception handlers (to include in error responses)

This is a foundational, non-business-logic middleware — safe to
implement fully in Phase 1.
"""

import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a unique ID, stored on `request.state`
    and echoed back in the response headers.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming_id or str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response