"""Request tracing middleware — adds request_id to logs and response headers."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store on request.state so exception handlers can access it
        request.state.request_id = request_id

        log = structlog.get_logger()
        start = time.monotonic()

        # Skip noisy health check logs
        is_health = request.url.path == "/api/v1/health"

        if not is_health:
            log.info(
                "request.start",
                method=request.method,
                path=request.url.path,
            )

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error(
                "request.error",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        if not is_health:
            log.info(
                "request.done",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        return response
