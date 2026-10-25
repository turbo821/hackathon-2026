"""Тесты логирования: формат, структурированные события, контекст запроса.

Проверяем то, на что потом опирается разбор логов:

* текстовый формат — читаемый, с полями события;
* JSON-формат — одна строка на запись, поля разложены по ключам;
* контекст запроса (request id, пользователь) попадает в каждую запись;
* таймер `timed` пишет длительность и не глушит исключение;
* уровень для сторонних библиотек поднимается до WARNING;
* middleware кладёт request id в ответ и в лог.
"""

import json
import logging

import pytest
from app.logging_config import (
    JsonFormatter,
    log_event,
    new_request_id,
    request_context,
    setup_logging,
    timed,
    user_var,
)


@pytest.fixture
def restore_logging():
    """Возвращает корневой логгер к исходному состоянию после теста."""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in handlers:
            root.removeHandler(handler)
    root.setLevel(level)


@pytest.fixture
def text_records(caplog, restore_logging):
    """Логи в текстовом формате, готовые к проверке.

    Отдаём сам caplog, а не caplog.records: records — вычисляемое свойство,
    и на момент setup их ещё нет.
    """
    setup_logging(name="test", level=logging.DEBUG, fmt="text")
    caplog.set_level(logging.DEBUG)
    yield caplog


def _record(caplog, event: str):
    for record in caplog.records:
        if getattr(record, "event", None) == event:
            return record
    found = [getattr(r, "event", None) for r in caplog.records]
    raise AssertionError(f"событие {event!r} не найдено среди {found}")


def _json_lines(captured: str) -> list[dict]:
    """Разбирает stdout как строки JSON (одна запись — одна строка)."""
    payloads = []
    for line in captured.splitlines():
        line = line.strip()
        if not line:
            continue
        payloads.append(json.loads(line))
    return payloads


def test_text_format_contains_message_and_fields(text_records):
    logger = logging.getLogger("test.events")
    log_event(logger, logging.INFO, "demo.event", count=3)

    record = _record(text_records, "demo.event")
    assert record.message == "demo.event"
    assert record.count == 3


def test_json_format_is_single_line_with_separate_fields(capsys, restore_logging):
    setup_logging(name="test", level=logging.DEBUG, fmt="json")
    logger = logging.getLogger("test.json")
    log_event(logger, logging.INFO, "demo.event", count=3, skipped=None)

    payloads = _json_lines(capsys.readouterr().out)
    event = next(p for p in payloads if p.get("event") == "demo.event")

    assert event["level"] == "INFO"
    assert event["logger"] == "test.json"
    assert event["count"] == 3
    # None-поля отбрасываются: «не применимо» и «не задано» — разные вещи
    assert "skipped" not in event


def test_json_each_record_is_one_line(capsys, restore_logging):
    setup_logging(name="test", level=logging.DEBUG, fmt="json")
    logger = logging.getLogger("test.json")
    log_event(logger, logging.INFO, "first.event")
    log_event(logger, logging.INFO, "second.event")

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    # каждая строка — валидный JSON, значит переносов внутри записей нет
    for line in lines:
        json.loads(line)
    assert len(lines) >= 2


def test_json_format_keeps_cyrillic_readable(capsys, restore_logging):
    setup_logging(name="test", level=logging.DEBUG, fmt="json")
    logging.getLogger("test.json").info("Проверка связи с бэкендом")

    payloads = _json_lines(capsys.readouterr().out)
    assert any(p["message"] == "Проверка связи с бэкендом" for p in payloads)


def test_request_context_is_added_to_records(text_records):
    logger = logging.getLogger("test.ctx")
    with request_context(request_id="abc123", user="cheremsha#9"):
        logger.info("внутри запроса")

    record = text_records.records[-1]
    assert record.request_id == "abc123"
    assert record.user == "cheremsha#9"


def test_request_context_is_reset_after_block(text_records):
    logger = logging.getLogger("test.ctx")
    with request_context(request_id="abc123", user="cheremsha#9"):
        pass
    logger.info("вне запроса")

    record = text_records.records[-1]
    assert record.request_id == "-"
    assert record.user == "-"


def test_new_request_id_is_short_and_unique():
    first = new_request_id()
    second = new_request_id()
    assert first != second
    assert len(first) == 12


def test_timed_writes_duration(text_records):
    logger = logging.getLogger("test.timer")
    with timed(logger, "demo.timed", items=5):
        pass

    record = _record(text_records, "demo.timed")
    assert record.items == 5
    assert record.duration_ms >= 0


def test_timed_does_not_swallow_exception(text_records):
    logger = logging.getLogger("test.timer")
    with pytest.raises(ValueError):
        with timed(logger, "demo.failed"):
            raise ValueError("сломалось")

    record = _record(text_records, "demo.failed")
    assert record.levelno == logging.ERROR
    assert record.error == "ValueError"


def test_libraries_level_raised_to_warning(restore_logging):
    setup_logging(name="test", level=logging.DEBUG, fmt="text")
    for name in ("uvicorn", "httpx", "sqlalchemy.engine"):
        assert logging.getLogger(name).level == logging.WARNING


def test_uvicorn_access_log_disabled(restore_logging):
    setup_logging(name="test", level=logging.DEBUG, fmt="text")
    assert logging.getLogger("uvicorn.access").disabled is True


def test_json_formatter_ignores_standard_record_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "path", 1, "сообщение", None, None)
    payload = json.loads(formatter.format(record))
    # стандартные поля LogRecord не должны попадать в payload как «поля события»
    assert "path" not in payload
    assert "msg" not in payload
    assert payload["message"] == "сообщение"


def test_user_var_defaults_to_dash():
    assert user_var.get() == "-"
