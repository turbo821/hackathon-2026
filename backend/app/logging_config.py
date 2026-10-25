"""Логирование приложения.

Только stdout: в Docker он попадает в `docker compose logs`, в systemd — в journal.
Файловые логи с ротацией для этого проекта не нужны (см. README).

Что даёт модуль:

* `setup_logging()` — настройка корневого логгера. Уровень берётся из LOG_LEVEL,
  формат — из LOG_FORMAT (`text` для разработки, `json` для сервера, чтобы
  логи нормально парсились).
* `get_logger()` — логгер модуля.
* `log_event()` — структурированное событие: положительные и отрицательные
  ключи пишутся в отдельные поля (в JSON) и в скобках (в текстовом формате).
* `request_context()` — контекст текущего запроса (request id, пользователь,
  метод, путь). Подкладывается middleware'ом, чтобы в любом логе внутри
  обработчика было видно, к какому запросу он относится.

Сторонние библиотеки (uvicorn, httpx, sqlalchemy) по умолгу пишут в root-логгер
и засоряют вывод. Их уровень задаётся отдельно через LOG_LEVEL_LIBRARIES,
по умолчанию WARNING — то есть видны только проблемы, а не рутина.
"""

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

# Контекст запроса: ContextVar вместо потоковых переменных — он корректно
# работает и в async-коде FastAPI (Task), где потоки общие.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
user_var: contextvars.ContextVar[str] = contextvars.ContextVar("user", default="-")

# Ключи контекста, которые попадают в каждую запись лога.
_CONTEXT_KEYS = ("request_id", "user")

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}

# Помечает обработчики, созданные нами: только их setup_logging удаляет при
# повторном вызове (чужие обработчики, например pytest caplog, остаются).
_OWN_HANDLER_ATTR = "_invoice_keeper_handler"

# Поля, которые добавляет фабрика записей: их нельзя передавать через extra
# (Python запрещает затирать поля LogRecord), и о них нельзя забыть.
_FACTORY_FIELDS = frozenset({"request_id", "user"})


def _install_record_factory() -> None:
    """Добавляет контекст запроса в каждую создаваемую запись.

    Сделано через фабрику записей, а не фильтром на обработчике: так поля
    видны всем обработчикам, включая перехватчик pytest (caplog) — иначе в
    тестах в записи не было бы request_id.
    """
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_invoice_keeper_context", False):
        return

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get()
        record.user = user_var.get()
        return record

    setattr(factory, "_invoice_keeper_context", True)
    logging.setLogRecordFactory(factory)


class JsonFormatter(logging.Formatter):
    """Каждая запись — одна строка JSON.

    Состав: время (ISO), уровень, логгер, сообщение, поля события и контекст
    запроса. Всё, что не является стандартным полем LogRecord, считается
    дополнительным полем события (см. log_event).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Человекочитаемый формат: время | уровень | логгер | сообщение | поля."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED
            and key != "event"  # событие уже стоит в сообщении
            and not key.startswith("_")
        }
        if extras:
            parts = " ".join(f"{key}={value}" for key, value in extras.items())
            base = f"{base} | {parts}"
        return base


def _env_level(name: str, default: str) -> int:
    raw = (os.getenv(name) or default).strip().upper()
    return getattr(logging, raw, logging.INFO) if raw.isalpha() else logging.INFO


def _setting(name: str, env_name: str) -> str:
    """Значение настройки: сначала app.config.settings, потом переменная окружения.

    Импорт внутри функции — app.config не должен зависеть от логирования,
    а логирование при этом обязано видеть настройки из .env.
    """
    try:
        from app.config import settings

        value = getattr(settings, name, "")
        if value:
            return str(value)
    except Exception:  # настройки ещё не загружены — берём из окружения
        pass
    return os.getenv(env_name, "")


def _level_from(value: str, default: int = logging.INFO) -> int:
    """Строка уровня -> число logging. Неизвестное значение -> default."""
    raw = (value or "").strip().upper()
    if not raw.isalpha():
        return default
    return getattr(logging, raw, default)


def setup_logging(
    name: str = "backend",
    level: int | None = None,
    fmt: str | None = None,
) -> None:
    """Настраивает корневой логгер. Вызывается один раз при старте процесса.

    Параметры `level` и `fmt` перекрывают переменные окружения LOG_LEVEL и
    LOG_FORMAT — это нужно тестам и скриптам.
    """
    root = logging.getLogger()
    root.setLevel(
        level
        if level is not None
        else _level_from(_setting("log_level", "LOG_LEVEL"), logging.INFO)
    )

    # Повторный вызов не должен дублировать записи. Удаляем только свои
    # обработчики: чужие (например, перехватчик pytest в caplog) не трогаем.
    for handler in list(root.handlers):
        if getattr(handler, _OWN_HANDLER_ATTR, False):
            root.removeHandler(handler)

    fmt = (fmt or _setting("log_format", "LOG_FORMAT") or "text").strip().lower()
    if fmt == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = TextFormatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    # Логи идут в stdout — так их видно в docker compose logs и в journalctl.
    # Диагностические скрипты печатают свой отчёт тоже в stdout; чтобы не
    # путать, отчёт они отделяют строкой-разделителем (см. scripts.check_*).
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    setattr(handler, _OWN_HANDLER_ATTR, True)
    root.addHandler(handler)

    # Контекст запроса — в фабрике записей, чтобы его видели все обработчики.
    _install_record_factory()

    # Сторонние библиотеки — по умолчанию только предупреждения и ошибки.
    libraries_level = _level_from(
        _setting("log_level_libraries", "LOG_LEVEL_LIBRARIES"), logging.WARNING
    )
    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "httpx",
        "httpcore",
        "sqlalchemy.engine",
        "aiosqlite",
    ):
        logging.getLogger(logger_name).setLevel(libraries_level)

    # uvicorn.access сам форматирует строку запроса — она нам не нужна,
    # потому что запросы логирует наш middleware (с request id и таймингом).
    logging.getLogger("uvicorn.access").disabled = True

    root.info(
        f"Логирование настроено для {name} (уровень {logging.getLevelName(root.level)}, формат {fmt})"
    )


def get_logger(name: str) -> logging.Logger:
    """Логгер для модуля: get_logger(__name__)"""
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    /,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    """Структурированное событие.

    `event` — короткое имя события (например, "reminder.sent"), поля — детали.
    В JSON-формате это отдельные ключи, в текстовом — `key=value` в конце строки.

    Поля со значением None отбрасываются: «не применимо» и «не задано» — разные
    вещи, и в логах это должно быть видно.
    """
    payload = {key: value for key, value in fields.items() if value is not None}
    payload["event"] = event
    # Стандартные поля LogRecord занимать нельзя: Python бросает KeyError
    # («Attempt to overwrite 'name' in LogRecord»). Такие поля переименовываем
    # с префиксом field_, чтобы ничего не потерялось.
    safe = {}
    for key, value in payload.items():
        if key in _RESERVED:
            key = f"field_{key}"
        if key in _FACTORY_FIELDS:
            # Поле уже есть в записи (его кладёт фабрика) — повторно передавать
            # нельзя, Python запрещает затирать поля LogRecord.
            continue
        safe[key] = value
    logger.log(level, event, exc_info=exc_info, extra=safe)


def log_event_with_context(
    logger: logging.Logger,
    level: int,
    event: str,
    /,
    request_id: str | None = None,
    user: str | None = None,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    """Событие с явным контекстом — когда он известен извне.

    Нужен там, где запись создаётся не в той задаче, где ставился контекст
    (например, middleware логирует обращение после обработчика).
    """
    original_request_id = request_id_var.get()
    original_user = user_var.get()
    try:
        if request_id is not None:
            request_id_var.set(request_id)
        if user is not None:
            user_var.set(user)
        log_event(logger, level, event, exc_info=exc_info, **fields)
    finally:
        request_id_var.set(original_request_id)
        user_var.set(original_user)


@contextmanager
def request_context(
    request_id: str | None = None, user: str | None = None
) -> Iterator[None]:
    """Привязывает контекст запроса ко всем записям внутри блока."""
    rid_token = request_id_var.set(request_id or uuid.uuid4().hex[:12])
    user_token = user_var.set(user or "-")
    try:
        yield
    finally:
        request_id_var.reset(rid_token)
        user_var.reset(user_token)


def new_request_id() -> str:
    """Короткий идентификатор запроса для связки записей в логах."""
    return uuid.uuid4().hex[:12]


def timed(logger: logging.Logger, event: str, /, **fields: Any) -> "_Timer":
    """Контекстный менеджер: замеряет время выполнения и пишет его в лог.

        with timed(logger, "reminder.check", occurrences=12):
            ...

    В лог попадает событие с полем `duration_ms`.
    """
    return _Timer(logger, event, fields)


class _Timer:
    def __init__(self, logger: logging.Logger, event: str, fields: dict[str, Any]):
        self._logger = logger
        self._event = event
        self._fields = fields
        self._start = 0.0

    def __enter__(self) -> "_Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = round((time.perf_counter() - self._start) * 1000, 1)
        level = logging.ERROR if exc_type is not None else logging.INFO
        fields = {**self._fields, "duration_ms": duration_ms}
        if exc_type is not None:
            fields["error"] = exc_type.__name__
        log_event(
            self._logger, level, self._event, exc_info=exc_type is not None, **fields
        )
        return False  # исключение не подавляем
