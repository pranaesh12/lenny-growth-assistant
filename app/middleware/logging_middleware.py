"""
Request/response logging middleware (Loguru-based).

Replaces the Phase 1 stdlib-logging version. Logs one structured line
per request with method, path, status code, response time, and client
IP. Relies on `request.state.request_id` being set by
`RequestIDMiddleware`, which must execute before this middleware (see
ordering note in `app/main.py`).
"""

import time
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.logger import get_logger

log = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs structured request/response metadata for every HTTP call."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_time = time.perf_counter()
        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log.bind(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                client_ip=client_ip,
                duration_ms=round(duration_ms, 2),
            ).exception("Unhandled exception during request processing")
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        log_bound = log.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=client_ip,
        )

        if response.status_code >= 500:
            log_bound.error("Request completed with server error")
        elif response.status_code >= 400:
            log_bound.warning("Request completed with client error")
        else:
            log_bound.info("Request completed")

        return response