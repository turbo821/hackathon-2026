"""Middleware: контекст запроса и журнал обращений.

Что делает RequestContextMiddleware:

* назначает каждому запросу короткий id (request id) и кладёт его в
  контекст — дальше любая запись лога внутри обработчика содержит этот id,
  и цепочку записей одного запроса можно найти по нему;
* запоминает пользователя (его проставляет обработчик авторизации —
  см. app.auth: там он кладётся и в контекст, и в request.state);
* после обработки пишет одну запись: метод, путь, статус, длительность,
  размер ответа.

Заголовок X-Request-ID кладу в ответ: по нему можно найти запрос и в логах
сервера, и в логах клиента (браузер покажет его в devtools).
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import (
    log_event_with_context,
    new_request_id,
    request_context,
)

logger = logging.getLogger("app.request")

HEADER_REQUEST_ID = "X-Request-ID"

# Пути, которые не стоит засорять журналом: служебные и частые.
QUIET_PATHS = frozenset({"/api/v1/health", "/api/hello", "/favicon.ico"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Присваиваем запросу метку request_id, чтобы в логах было видно,
        # чей это запрос. Роли и имя пользователя проставит app.auth.
        incoming = request.headers.get(HEADER_REQUEST_ID)
        request_id = incoming if incoming and len(incoming) <= 64 else new_request_id()
        request.state.request_id = request_id

        token = request_context(request_id=request_id)
        token.__enter__()
        started = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            response.headers[HEADER_REQUEST_ID] = request_id
            self._log(request, response, duration_ms, None)
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            self._log(request, None, duration_ms, exc)
            raise
        finally:
            token.__exit__(None, None, None)

    def _log(
        self,
        request: Request,
        response: Response | None,
        duration_ms: float,
        exc: Exception | None,
    ) -> None:
        path = request.url.path
        if path in QUIET_PATHS:
            return

        status = response.status_code if response is not None else 500
        level = logging.INFO
        if exc is not None or status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING

        # Пользователя кладёт app.auth в request.state: контекст задачи
        # обработчика к моменту логирования уже не тот, поэтому берём
        # значение явно.
        user = getattr(request.state, "user_ref", None)

        log_event_with_context(
            logger,
            level,
            "http.request",
            request_id=getattr(request.state, "request_id", None),
            user=user,
            method=request.method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
            error=type(exc).__name__ if exc is not None else None,
            exc_info=exc is not None,
        )
