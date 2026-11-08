"""Consistent error envelope: {"error": {"code", "message", "message_ar", "details", "request_id"}}."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("rip.errors")


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, message_ar: str = "", details: dict | None = None, status_code: int | None = None,
                 code: str | None = None):
        super().__init__(message)
        self.message = message
        self.message_ar = message_ar or message
        self.details = details or {}
        if status_code:
            self.status_code = status_code
        if code:
            self.code = code


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, what: str = "Resource", what_ar: str = "المورد"):
        super().__init__(f"{what} not found", f"{what_ar} غير موجود")


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"

    def __init__(self, message: str = "You do not have permission to perform this action",
                 message_ar: str = "ليست لديك صلاحية لتنفيذ هذا الإجراء", details: dict | None = None):
        super().__init__(message, message_ar, details)


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"

    def __init__(self, message: str = "Authentication required", message_ar: str = "يلزم تسجيل الدخول"):
        super().__init__(message, message_ar)


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"

    def __init__(self):
        super().__init__("Too many requests", "عدد الطلبات تجاوز الحد المسموح، يرجى المحاولة لاحقاً")


def _envelope(request: Request, status: int, code: str, message: str, message_ar: str, details=None) -> JSONResponse:
    rid = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "message_ar": message_ar, "details": details or {}, "request_id": rid}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.message_ar, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errs = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return _envelope(request, 422, "VALIDATION_ERROR", "Request validation failed", "البيانات المدخلة غير صحيحة", {"errors": errs})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return _envelope(request, exc.status_code, "HTTP_ERROR", str(exc.detail), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", "")})
        return _envelope(request, 500, "INTERNAL_ERROR", "An unexpected error occurred", "حدث خطأ غير متوقع")
