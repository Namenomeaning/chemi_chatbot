import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.config import DEFAULT_ORIGINS
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def error_response(request, status, code, message, headers=None):
    headers = dict(headers or {})
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id
    origin = request.headers.get("origin")
    env = request.scope.get("env")
    configured = getattr(env, "CORS_ORIGINS", "") if env else ""
    allowed = [value.strip() for value in configured.split(",")] if configured else DEFAULT_ORIGINS
    if origin and origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Expose-Headers"] = "X-Request-ID"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=status,
        content={
            "success": False,
            "error": message,
            "error_code": code,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers=headers,
    )


async def app_error_handler(request: Request, exc: AppError):
    return error_response(request, exc.status_code, exc.code, exc.message)


async def http_error_handler(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail), exc.headers)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Do not echo input values: validation errors can contain credentials or image data.
    return error_response(request, 422, "INVALID_REQUEST", "The request contains invalid fields.")


async def unexpected_error_handler(request: Request, exc: Exception):
    # A type and request id allow correlation without logging provider URLs or API keys.
    logger.error(
        "request_failed request_id=%s exception_type=%s", getattr(request.state, "request_id", None), type(exc).__name__
    )
    return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
