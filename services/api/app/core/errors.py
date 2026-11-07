from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 400
    code = "error"
    default_message = "Request failed"

    def __init__(self, message: str = "", field: str | None = None):
        self.message = message or self.default_message
        self.field = field
        super().__init__(self.message)


class Unauthenticated(AppError):
    status_code = 401
    code = "unauthenticated"
    default_message = "Authentication required"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    default_message = "You do not have permission to do this"


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    default_message = "Resource not found"


class StaleRevision(AppError):
    status_code = 409
    code = "stale_revision"
    default_message = "The resource changed; reload and retry"


class IdempotencyConflict(AppError):
    status_code = 409
    code = "idempotency_conflict"
    default_message = "Idempotency-Key conflict"


class AppValidationError(AppError):
    status_code = 422
    code = "validation_error"
    default_message = "Invalid request"


def error_body(code: str, message: str, field: str | None = None) -> dict:
    err = {"code": code, "message": message}
    if field:
        err["field"] = field
    return {"data": None, "error": err}


_HTTP_CODES = {401: "unauthenticated", 403: "forbidden", 404: "not_found",
               405: "method_not_allowed"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message, exc.field), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {"loc": (), "msg": "Invalid request"}
        parts = [str(p) for p in first["loc"] if p not in ("body", "query", "path", "header")]
        return JSONResponse(
            error_body("validation_error", str(first["msg"]), ".".join(parts) or None), 422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            error_body(code, str(exc.detail)), exc.status_code, headers=exc.headers
        )
