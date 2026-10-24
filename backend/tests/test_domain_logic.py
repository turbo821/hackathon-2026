"""Сценарии из критериев приёмки, которым нужна доменная логика:
генерация периодов, статусы и просрочка, напоминания в Telegram.

Отправка в Telegram здесь подменена (фикстура `sent`), реальных сообщений
тесты не шлют.
"""

from datetime import date
from decimal import Decimal

import pytest

from app import timeutils
from app.models import RecurringPayment
from app.services import telegram
from app.services.reminders import check_and_send
from tests.conftest import login

API = "/api/v1"


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram и копит тексты сообщений."""
    messages = []
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda text, chat_id=None, reply_markup=None: messages.append(text) or {"ok": True},
    )
    return messages


def create_payment(client, headers, **overrides):
    body = {"name": "Аренда", "amount": "50000", "currency": "RUB", "first_due_date": "2026-10-25"}
    body.update(overrides)
    r = client.post(f"{API}/recurring-payments", json=body, headers=headers)
    assert r.status_code == 201, r.json()
    return r.json()


def occurrences(client, headers, **params):
    r = client.get(f"{API}/payment-occurrences", params=params, headers=headers)
    assert r.status_code == 200, r.json()
    return r.json()


# ---------- Роли (полная версия) ----------


def test_user_cannot_do_admin_actions_via_api(client, admin, user):
    rp = create_payment(client, admin)
    assert client.post(f"{API}/recurring-payments", json={"name": "x", "amount": 1, "currency": "RUB",
                                                         "first_due_date": "2026-11-01"}, headers=user).status_code == 403
    assert client.delete(f"{API}/recurring-payments/{rp['id']}", headers=user).status_code == 403
    assert client.get(f"{API}/users", headers=user).status_code == 403
    assert client.post(f"{API}/users", json={"username": "hack", "password": "123456"}, headers=user).status_code == 403
    # а смотреть и отмечать оплату — можно
    assert client.get(f"{API}/recurring-payments", headers=user).status_code == 200
    occ = occurrences(client, user)[0]
    r = client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "paid"}, headers=user)
    assert r.status_code == 200 and r.json()["status"] == "paid"


# ---------- Регулярность ----------


def test_next_period_has_own_status_and_history_kept(client, admin):
    rp = create_payment(client, admin, first_due_date="2026-10-25")
    occs = occurrences(client, admin, recurring_payment_id=rp["id"])
    assert [o["due_date"] for o in occs] == ["2026-10-25"]

    client.patch(f"{API}/payment-occurrences/{occs[0]['id']}", json={"status": "paid"}, headers=admin)
    occs = occurrences(client, admin, recurring_payment_id=rp["id"])
    assert [(o["due_date"], o["status"]) for o in occs] == [
        ("2026-10-25", "paid"),
        ("2026-11-25", "unpaid"),  # следующий период — с отдельным статусом
    ]

    # Прошёл месяц: прошлые периоды сохраняются
    timeutils.FROZEN_TODAY = date(2026, 12, 1)
    occs = occurrences(client, admin, recurring_payment_id=rp["id"])
    assert [(o["due_date"], o["state"]) for o in occs] == [
        ("2026-10-25", "paid"),
        ("2026-11-25", "overdue"),
        ("2026-12-25", "pending"),  # просрочка не останавливает следующие периоды
    ]


def test_past_first_date_generates_history(client, admin):
    rp = create_payment(client, admin, first_due_date="2026-07-31")
    dates = [o["due_date"] for o in occurrences(client, admin, recurring_payment_id=rp["id"])]
    assert dates == ["2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31"]


# ---------- Статусы и просрочка ----------


def test_overdue_rules_and_paid_at_correction(client, admin):
    rp = create_payment(client, admin, first_due_date="2026-10-20")
    occ = occurrences(client, admin, recurring_payment_id=rp["id"])[0]
    assert occ["state"] == "overdue" and occ["overdue_days"] == 3

    # Оплатили сегодня (позже срока) → оплачено с опозданием
    r = client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "paid"}, headers=admin)
    assert r.json()["state"] == "paid_late" and r.json()["paid_at"] == "2026-10-23"

    # Исправили дату на день срока → просрочка исчезла, срок не изменился
    r = client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"paid_at": "2026-10-20"}, headers=admin)
    assert r.json()["state"] == "paid" and r.json()["overdue_days"] == 0 and r.json()["due_date"] == "2026-10-20"

    # Отмена отметки → дата очищается
    r = client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "unpaid"}, headers=admin)
    assert r.json()["status"] == "unpaid" and r.json()["paid_at"] is None and r.json()["state"] == "overdue"


def test_patch_validation(client, admin):
    rp = create_payment(client, admin)
    occ = occurrences(client, admin, recurring_payment_id=rp["id"])[0]
    url = f"{API}/payment-occurrences/{occ['id']}"
    assert client.patch(url, json={"paid_at": "2026-10-20"}, headers=admin).status_code == 409
    assert client.patch(url, json={"status": "paid", "paid_at": "2030-01-01"}, headers=admin).status_code == 422
    assert client.patch(url, json={}, headers=admin).status_code == 422
    assert client.get(f"{API}/payment-occurrences/99999", headers=admin).status_code == 404


def test_state_filter(client, admin):
    create_payment(client, admin, name="Просрочен", first_due_date="2026-10-01")
    create_payment(client, admin, name="Будущий", first_due_date="2026-11-10")
    overdue = occurrences(client, admin, state="overdue")
    assert {o["name"] for o in overdue} == {"Просрочен"}


# ---------- Напоминания ----------


def test_reminder_sent_immediately_when_added_late(client, admin, sent):
    create_payment(client, admin, name="Сервер", amount="20", currency="USD", first_due_date="2026-10-25")
    assert len(sent) == 1
    assert "Сервер" in sent[0] and "20.00 USD" in sent[0] and "25.10.2026" in sent[0]


def test_worker_creates_missing_periods(client, admin, sent, db):
    """Платёж, созданный мимо API, worker тоже должен увидеть: периоды досоздаются."""
    db.add(
        RecurringPayment(
            name="Сервер", amount=Decimal("49.90"), currency="USD", period="monthly",
            first_due_date=date(2026, 10, 25), anchor_day=25,
        )
    )
    db.commit()
    assert check_and_send(db) == 1
    assert len(sent) == 1 and "Сервер" in sent[0]


def test_reminder_window_and_no_duplicates(client, admin, sent, db):
    create_payment(client, admin, first_due_date="2026-11-10")  # далеко — без напоминания
    assert sent == []

    timeutils.FROZEN_TODAY = date(2026, 11, 6)  # за 4 дня — рано
    check_and_send(db)
    assert sent == []

    timeutils.FROZEN_TODAY = date(2026, 11, 7)  # за 3 дня — пора
    check_and_send(db)
    check_and_send(db)  # повторная проверка не создаёт дубль
    timeutils.FROZEN_TODAY = date(2026, 11, 8)
    check_and_send(db)
    assert len(sent) == 1


def test_paid_period_not_reminded(client, admin, sent, db):
    rp = create_payment(client, admin, first_due_date="2026-11-10")
    occ = occurrences(client, admin, recurring_payment_id=rp["id"])[0]
    client.patch(f"{API}/payment-occurrences/{occ['id']}", json={"status": "paid"}, headers=admin)
    timeutils.FROZEN_TODAY = date(2026, 11, 8)
    check_and_send(db)
    assert sent == []


def test_deleted_payment_not_reminded_history_kept(client, admin, sent, db):
    rp = create_payment(client, admin, first_due_date="2026-09-10")  # сентябрь просрочен, октябрь тоже
    assert client.delete(f"{API}/recurring-payments/{rp['id']}", headers=admin).status_code == 204
    assert client.delete(f"{API}/recurring-payments/{rp['id']}", headers=admin).status_code == 404

    timeutils.FROZEN_TODAY = date(2026, 11, 8)
    check_and_send(db)
    assert sent == []

    occs = occurrences(client, admin, recurring_payment_id=rp["id"])
    assert [o["due_date"] for o in occs] == ["2026-09-10", "2026-10-10"]  # история осталась
    assert all(o["payment_ended_at"] is not None for o in occs)
    assert client.get(f"{API}/recurring-payments", headers=admin).json() == []
    assert len(client.get(f"{API}/recurring-payments?include_inactive=true", headers=admin).json()) == 1


def test_failed_telegram_send_is_retried(client, admin, monkeypatch, db):
    calls = []

    def flaky(text, chat_id=None, reply_markup=None):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("network down")
        return {"ok": True}

    monkeypatch.setattr(telegram, "send_message", flaky)
    create_payment(client, admin, first_due_date="2026-10-25")  # первая попытка падает
    check_and_send(db)  # вторая — успешна
    check_and_send(db)  # дубля нет
    assert len(calls) == 2


# ---------- Валюты ----------


def test_summary_per_currency_without_conversion(client, admin):
    create_payment(client, admin, name="Аренда", amount="1000.50", currency="RUB", first_due_date="2026-10-20")
    create_payment(client, admin, name="Сервер", amount="20", currency="USD", first_due_date="2026-10-28")
    rp = create_payment(client, admin, name="Подписка", amount="15.99", currency="EUR", first_due_date="2026-10-01")
    eur = occurrences(client, admin, recurring_payment_id=rp["id"])[0]
    client.patch(f"{API}/payment-occurrences/{eur['id']}", json={"status": "paid", "paid_at": "2026-10-01"}, headers=admin)

    s = client.get(f"{API}/payments/summary?date_from=2026-10-01&date_to=2026-10-31", headers=admin).json()
    by = {c["currency"]: c for c in s["currencies"]}
    assert by["RUB"]["total"] == "1000.50" and by["RUB"]["overdue"] == "1000.50"
    assert by["USD"]["unpaid"] == "20.00" and by["USD"]["overdue"] == "0.00"
    assert by["EUR"]["paid"] == "15.99" and by["EUR"]["unpaid"] == "0.00"
