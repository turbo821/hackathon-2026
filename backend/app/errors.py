"""Единый формат ошибок API (фронтенд на него рассчитан).

    {"code": 403, "status": "Forbidden", "message": "Действие доступно только администратору"}
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger(__name__)


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


def _body(code: int, message: str) -> dict:
    # В Python 3.13 422 называется «Unprocessable Content»; оставляем прежнее название
    phrase = "Unprocessable Entity" if code == 422 else HTTPStatus(code).phrase
    return {"code": code, "status": phrase, "message": message}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.code)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return JSONResponse(_body(exc.status_code, message), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        message = errors[0].get("msg", "Некорректный запрос") if errors else "Некорректный запрос"
        # Свои ValueError в валидаторах pydantic оборачивает в «Value error, …»
        return JSONResponse(_body(422, message.removeprefix("Value error, ")), status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception(f"Необработанная ошибка: {request.method} {request.url.path}")
        return JSONResponse(_body(500, "Внутренняя ошибка сервера"), status_code=500)
