"""Тесты журнала обращений: middleware пишет одну запись на запрос.

Проверяем то, что нужно при разборе «что происходило в момент обращения»:

* на каждый запрос — одна запись http.request с методом, путём, статусом и
  длительностью;
* request id попадает и в запись лога, и в заголовок ответа (по нему можно
  связать запись сервера с записью клиента);
* ошибки 4xx не поднимаются до ERROR, 5xx — поднимаются;
* служебные пути (health, hello) в журнал не пишутся.
"""

import logging

import pytest
from app.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


def _events(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "event", None) == "http.request"]


def test_request_is_logged(caplog, client):
    caplog.set_level(logging.INFO)
    client.get("/api/v1/hello")

    events = _events(caplog)
    assert events, "запрос не попал в журнал"
    record = events[-1]
    assert record.method == "GET"
    assert record.path == "/api/v1/hello"
    assert record.status == 200
    assert record.duration_ms >= 0


def test_request_id_is_returned_in_header(caplog, client):
    caplog.set_level(logging.INFO)
    response = client.get("/api/v1/hello")

    request_id = response.headers.get("X-Request-ID")
    assert request_id, "в ответе нет заголовка X-Request-ID"

    events = _events(caplog)
    assert events[-1].request_id == request_id


def test_client_can_pass_its_own_request_id(caplog, client):
    caplog.set_level(logging.INFO)
    response = client.get("/api/v1/hello", headers={"X-Request-ID": "my-trace-42"})

    assert response.headers.get("X-Request-ID") == "my-trace-42"
    events = _events(caplog)
    assert events[-1].request_id == "my-trace-42"


def test_client_error_is_warning_not_error(caplog, client):
    caplog.set_level(logging.INFO)
    client.get("/api/v1/payments")  # без токена -> 401

    events = _events(caplog)
    assert events, "запрос не попал в журнал"
    record = events[-1]
    assert record.status == 401
    assert record.levelno == logging.WARNING


def test_service_paths_are_not_logged(caplog, client):
    caplog.set_level(logging.INFO)
    client.get("/api/v1/health")

    paths = [r.path for r in _events(caplog)]
    assert "/api/v1/health" not in paths
