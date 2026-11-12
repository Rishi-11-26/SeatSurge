"""
Centralised exception handlers for SeatSurge FastAPI application.

All HTTP errors and request validation failures are serialised into the
agreed structured error envelope defined in schemas/error.py and in the
API contract (docs/api-contract.md):

    {"error": {"code": "...", "message": "...", "details": {}, "timestamp": "..."}}

Usage:
    from app.core.exceptions import register_exception_handlers
    register_exception_handlers(app)
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorDetail, ErrorResponse

# Maps HTTP status codes to machine-readable error codes
_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "GONE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach structured error response handlers to a FastAPI application.

    Call once per app instance (main app and any test mini-apps that need
    consistent error formatting).
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_CODE_MAP.get(exc.status_code, "ERROR")
        # exc.detail may be a plain string or a structured dict
        if isinstance(exc.detail, str):
            message = exc.detail
            details: dict = {}
        elif isinstance(exc.detail, dict):
            message = exc.detail.get("message", "An error occurred.")
            details = {k: v for k, v in exc.detail.items() if k != "message"}
        else:
            message = "An error occurred."
            details = {}

        body = ErrorResponse(
            error=ErrorDetail(code=code, message=message, details=details)
        )
        # Preserve headers (e.g. Retry-After on 429)
        response_headers = getattr(exc, "headers", None) or {}
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(),
            headers=response_headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed. Check 'details' for field-level errors.",
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump())
