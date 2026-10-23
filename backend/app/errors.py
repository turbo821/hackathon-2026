"""Единый формат ошибок API (фронтенд на него рассчитан).

    {"code": 403, "status": "Forbidden", "message": "Действие доступно только администратору"}
    {"code": 422, "status": "Unprocessable Entity", "message": "...",
     "errors": {"json": {"amount": ["Сумма должна быть больше нуля"]}}}
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


def _phrase(code: int) -> str:
    # В Python 3.13 422 называется «Unprocessable Content»; оставляем прежнее название
    return "Unprocessable Entity" if code == 422 else HTTPStatus(code).phrase


def _body(code: int, message: str, errors: dict | None = None) -> dict:
    body = {"code": code, "status": _phrase(code), "message": message}
    if errors:
        body["errors"] = errors
    return body


# Перевод типовых сообщений pydantic
_MESSAGES = {
    "missing": "Обязательное поле",
    "date_from_datetime_parsing": "Дата в формате ГГГГ-ММ-ДД",
    "date_parsing": "Дата в формате ГГГГ-ММ-ДД",
    "date_type": "Дата в формате ГГГГ-ММ-ДД",
    "int_parsing": "Нужно целое число",
    "bool_parsing": "Нужно true или false",
    "string_type": "Нужна строка",
    "json_invalid": "Некорректный JSON",
    "model_attributes_type": "Ожидается JSON-объект",
}

# Где лежало поле — в терминах прежнего API (json / query / path)
_LOCATIONS = {"body": "json", "query": "query", "path": "path"}


def _message(err: dict) -> str:
    if err["type"] in _MESSAGES:
        return _MESSAGES[err["type"]]
    if err["type"] == "literal_error":
        expected = err.get("ctx", {}).get("expected", "")
        return f"Допустимые значения: {expected}"
    msg = err.get("msg", "Некорректное значение")
    # Свои ValueError в валидаторах pydantic оборачивает в «Value error, …»
    return msg.removeprefix("Value error, ").removeprefix("Assertion failed, ")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.code)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        if exc.status_code == 404 and message == "Not Found":
            message = "Не найдено"
        return JSONResponse(_body(exc.status_code, message), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors: dict[str, dict[str, list[str]]] = {}
        for err in exc.errors():
            loc = list(err["loc"])
            where = _LOCATIONS.get(loc[0], loc[0]) if loc else "json"
            field = ".".join(str(p) for p in loc[1:]) or "_schema"
            errors.setdefault(where, {}).setdefault(field, []).append(_message(err))
        first = next(iter(next(iter(errors.values())).values()))[0] if errors else "Некорректный запрос"
        return JSONResponse(_body(422, first, errors), status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception(f"Необработанная ошибка: {request.method} {request.url.path}")
        return JSONResponse(_body(500, "Внутренняя ошибка сервера"), status_code=500)
