"""Сценарии из критериев приёмки кейса."""

from datetime import date

from app import timeutils
from app.services.reminders import check_and_send
from tests.conftest import login

API = "/api/v1"


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


# ---------- Запуск и доступ ----------


def test_no_access_without_auth(client):
    for method, url in [
        ("get", "/recurring-payments"),
        ("get", "/payment-occurrences"),
        ("get", "/payment-occurrences/1"),
        ("get", "/payments/summary"),
        ("get", "/users"),
        ("get", "/auth/me"),
        ("post", "/recurring-payments"),
    ]:
        r = getattr(client, method)(API + url)
        assert r.status_code == 401, (method, url)


def test_login_me_logout(client):
    assert client.post(f"{API}/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    headers = login(client, "admin", "admin-pass")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["role"] == "admin" and me["is_env_admin"] is True
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_swagger_and_spec(client):
    assert client.get(f"{API}/docs").status_code == 200
    spec = client.get(f"{API}/openapi.json").json()
    for path in ["/api/v1/auth/login", "/api/v1/recurring-payments/{payment_id}",
                 "/api/v1/payment-occurrences/{occurrence_id}", "/api/v1/payments/summary",
                 "/api/v1/users/{user_id}"]:
        assert path in spec["paths"]


# ---------- Роли ----------


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


def test_env_admin_cannot_be_managed(client, admin):
    users = client.get(f"{API}/users", headers=admin).json()
    admin_id = next(u["id"] for u in users if u["is_env_admin"])
    assert client.patch(f"{API}/users/{admin_id}", json={"password": "newpass1"}, headers=admin).status_code == 403
    assert client.delete(f"{API}/users/{admin_id}", headers=admin).status_code == 403


def test_user_crud(client, admin):
    r = client.post(f"{API}/users", json={"username": "petr", "password": "petr12345"}, headers=admin)
    assert r.status_code == 201 and r.json()["role"] == "user"
    uid = r.json()["id"]
    assert client.post(f"{API}/users", json={"username": "petr", "password": "x123456"}, headers=admin).status_code == 409
    assert client.patch(f"{API}/users/{uid}", json={"password": "newpass1"}, headers=admin).status_code == 200
    login(client, "petr", "newpass1")
    assert client.delete(f"{API}/users/{uid}", headers=admin).status_code == 204
    assert client.post(f"{API}/auth/login", json={"username": "petr", "password": "newpass1"}).status_code == 401


def test_deleted_user_token_stops_working(client, admin):
    r = client.post(f"{API}/users", json={"username": "temp", "password": "temp12345"}, headers=admin)
    headers = login(client, "temp", "temp12345")
    client.delete(f"{API}/users/{r.json()['id']}", headers=admin)
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


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
    assert all(o["recurring_payment_active"] is False for o in occs)
    assert client.get(f"{API}/recurring-payments", headers=admin).json() == []
    assert len(client.get(f"{API}/recurring-payments?include_inactive=true", headers=admin).json()) == 1


def test_failed_telegram_send_is_retried(client, admin, monkeypatch, db):
    from app.services import telegram

    calls = []

    def flaky(text, chat_id=None):
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


def test_amount_validation(client, admin):
    for bad in ["-5", "0", "abc", "10.123"]:
        r = client.post(f"{API}/recurring-payments", json={"name": "x", "amount": bad, "currency": "RUB",
                                                          "first_due_date": "2026-11-01"}, headers=admin)
        assert r.status_code == 422, bad
    r = client.post(f"{API}/recurring-payments", json={"name": "x", "amount": "5", "currency": "GBP",
                                                      "first_due_date": "2026-11-01"}, headers=admin)
    assert r.status_code == 422


def test_audit_log(client, admin):
    create_payment(client, admin)
    actions = [e["action"] for e in client.get(f"{API}/audit-logs", headers=admin).json()]
    assert "recurring_payment.create" in actions and "auth.login" in actions


def test_error_format_matches_frontend_contract(client, admin):
    r = client.post(f"{API}/recurring-payments", json={"name": "x", "amount": "-1", "currency": "GBP"}, headers=admin)
    body = r.json()
    assert r.status_code == 422 and body["code"] == 422 and body["status"] == "Unprocessable Entity"
    fields = body["errors"]["json"]
    assert fields["amount"] == ["Сумма должна быть больше нуля"]
    assert fields["first_due_date"] == ["Обязательное поле"]
    assert "currency" in fields
    assert body["message"]  # первое сообщение — для тоста на фронте

    r = client.get(f"{API}/users", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and r.json()["message"] == "Недействительный токен"
