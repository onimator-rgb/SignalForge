"""Custom exceptions and FastAPI exception handlers."""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.error_buffer import record_error
from app.logging_config import get_logger

log = get_logger(__name__)


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


class AppError(Exception):
    def __init__(self, detail: str, status_code: int = 500, error_code: str | None = None):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404, error_code="NOT_FOUND")


class ValidationError(AppError):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail=detail, status_code=422, error_code="VALIDATION_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _get_request_id(request)
        log.warning(
            "request.app_error",
            detail=exc.detail,
            status_code=exc.status_code,
            error_code=exc.error_code,
        )
        if exc.status_code >= 500:
            record_error(
                event="request.app_error",
                error=exc.detail,
                request_id=request_id,
                path=str(request.url.path),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)
        log.error(
            "request.unhandled_error",
            error=str(exc),
            path=str(request.url.path),
            exc_info=True,
        )
        record_error(
            event="request.unhandled_error",
            error=str(exc),
            request_id=request_id,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )
