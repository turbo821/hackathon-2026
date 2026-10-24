"""Сценарии из критериев приёмки, которые работают уже сейчас:

- запуск и доступ (без авторизации ничего не доступно);
- вход, текущий пользователь, выход;
- три роли (superadmin / admin / user) и ограничения, которые действуют и в API;
- Swagger и OpenAPI-спецификация;
- единый формат ошибок.

Сценарии, которым нужна доменная логика (периоды, напоминания), —
в файле tests/test_domain_logic.py.
"""

from fastapi.testclient import TestClient  # noqa: F401

from tests.conftest import login

API = "/api/v1"


def create_payment(client, headers, **overrides):
    body = {
        "name": "Аренда",
        "amount": "50000",
        "currency": "RUB",
        "first_due_date": "2026-10-25",
    }
    body.update(overrides)
    r = client.post(f"{API}/recurring-payments", json=body, headers=headers)
    assert r.status_code == 201, r.json()
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
    bad = client.post(f"{API}/auth/login", json={"email": "root@example.com", "password": "bad"})
    assert bad.status_code == 401
    # по логину больше не входят
    assert client.post(f"{API}/auth/login", json={"username": "root", "password": "root-pass"}).status_code == 422
    # email без учёта регистра и пробелов
    headers = login(client, " Root@Example.com ", "root-pass")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["role"] == "superadmin"
    assert me["email"] == "root@example.com"
    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_swagger_and_spec(client):
    assert client.get(f"{API}/docs").status_code == 200
    spec = client.get(f"{API}/openapi.json").json()
    for path in [
        "/api/v1/auth/login",
        "/api/v1/recurring-payments/{payment_id}",
        "/api/v1/payment-occurrences/{occurrence_id}",
        "/api/v1/payments/summary",
        "/api/v1/users/{user_id}",
    ]:
        assert path in spec["paths"]


def test_health_and_hello(client):
    assert client.get(f"{API}/health").json()["status"] == "ok"
    assert client.get(f"{API}/hello").json()["message"]
    # совместимость с фронтом, у которого baseURL по умолчанию /api
    assert client.get("/api/hello").json()["message"]


# ---------- Роли ----------


def test_user_cannot_do_admin_actions_via_api(client, admin, user):
    rp = create_payment(client, admin)
    body = {"name": "x", "amount": 1, "currency": "RUB", "first_due_date": "2026-11-01"}
    assert (
        client.post(f"{API}/recurring-payments", json=body, headers=user).status_code
        == 403
    )
    assert (
        client.delete(f"{API}/recurring-payments/{rp['id']}", headers=user).status_code
        == 403
    )
    assert client.get(f"{API}/users", headers=user).status_code == 403
    assert (
        client.post(
            f"{API}/users",
            json={
                "username": "hack",
                "password": "123456",
                "email": "hack@example.com",
            },
            headers=user,
        ).status_code
        == 403
    )
    # а смотреть платежи — можно
    assert client.get(f"{API}/recurring-payments", headers=user).status_code == 200


def test_superadmin_has_admin_and_user_rights(client, superadmin):
    rp = create_payment(client, superadmin)
    assert client.get(f"{API}/recurring-payments", headers=superadmin).status_code == 200
    assert client.get(f"{API}/payment-occurrences", headers=superadmin).status_code == 200
    assert client.get(f"{API}/users", headers=superadmin).status_code == 200
    r = client.post(f"{API}/users", json={"username": "kate", "password": "kate12345",
                                         "email": "kate@example.com"}, headers=superadmin)
    assert r.status_code == 201 and r.json()["role"] == "user"
    assert client.delete(f"{API}/recurring-payments/{rp['id']}", headers=superadmin).status_code == 204


def test_superadmin_cannot_be_managed(client, superadmin, admin):
    users = client.get(f"{API}/users", headers=superadmin).json()
    su_id = next(u["id"] for u in users if u["role"] == "superadmin")
    for headers in (superadmin, admin):
        assert client.patch(f"{API}/users/{su_id}", json={"password": "newpass1"}, headers=headers).status_code == 403
        assert client.delete(f"{API}/users/{su_id}", headers=headers).status_code == 403


def test_only_superadmin_manages_admins(client, superadmin, admin):
    body = {"username": "boss2", "password": "boss12345", "email": "boss2@example.com", "role": "admin"}
    # администратор не может создать администратора
    assert client.post(f"{API}/users", json=body, headers=admin).status_code == 403
    r = client.post(f"{API}/users", json=body, headers=superadmin)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    other_id = r.json()["id"]

    # администратор не управляет другими администраторами
    assert client.patch(f"{API}/users/{other_id}", json={"password": "newpass1"}, headers=admin).status_code == 403
    assert client.delete(f"{API}/users/{other_id}", headers=admin).status_code == 403

    # администратор не может повысить пользователя
    u = client.post(f"{API}/users", json={"username": "vasya", "password": "vasya12345",
                                         "email": "vasya@example.com"}, headers=admin).json()
    assert u["role"] == "user"
    assert client.patch(f"{API}/users/{u['id']}", json={"role": "admin"}, headers=admin).status_code == 403

    # суперадмин — может повысить и понизить
    assert client.patch(f"{API}/users/{u['id']}", json={"role": "admin"}, headers=superadmin).json()["role"] == "admin"
    assert client.patch(f"{API}/users/{other_id}", json={"role": "user"}, headers=superadmin).json()["role"] == "user"
    assert client.delete(f"{API}/users/{other_id}", headers=superadmin).status_code == 204

    # роль superadmin через API не назначить
    r = client.post(f"{API}/users", json={**body, "username": "boss3", "email": "boss3@example.com",
                                         "role": "superadmin"}, headers=superadmin)
    assert r.status_code == 422


def test_user_crud(client, admin):
    r = client.post(
        f"{API}/users",
        json={"username": "petr", "password": "petr12345", "email": "petr@example.com"},
        headers=admin,
    )
    assert r.status_code == 201 and r.json()["role"] == "user"
    uid = r.json()["id"]
    assert client.post(f"{API}/users", json={"username": "petr", "password": "x123456",
                                            "email": "other@example.com"}, headers=admin).status_code == 409
    assert client.patch(f"{API}/users/{uid}", json={"password": "newpass1"}, headers=admin).status_code == 200
    login(client, "petr@example.com", "newpass1")
    assert client.delete(f"{API}/users/{uid}", headers=admin).status_code == 204
    r = client.post(f"{API}/auth/login", json={"email": "petr@example.com", "password": "newpass1"})
    assert r.status_code == 401


def test_user_email_required_and_unique(client, admin):
    base = {"username": "olga", "password": "olga12345"}
    assert (
        client.post(f"{API}/users", json=base, headers=admin).status_code == 422
    )  # без email
    assert (
        client.post(
            f"{API}/users", json={**base, "email": "bad"}, headers=admin
        ).status_code
        == 422
    )
    r = client.post(
        f"{API}/users", json={**base, "email": " Olga@Example.com "}, headers=admin
    )
    assert r.status_code == 201 and r.json()["email"] == "olga@example.com"
    # занят без учёта регистра; логин и email суперадмина зарезервированы
    assert client.post(f"{API}/users", json={"username": "olga2", "password": "olga12345",
                                            "email": "OLGA@example.com"}, headers=admin).status_code == 409
    assert client.post(f"{API}/users", json={"username": "olga3", "password": "olga12345",
                                            "email": "root@example.com"}, headers=admin).status_code == 409
    assert client.post(f"{API}/users", json={"username": "root", "password": "olga12345",
                                            "email": "r@example.com"}, headers=admin).status_code == 409
    uid = r.json()["id"]
    r = client.patch(f"{API}/users/{uid}", json={"email": "o@ex.com"}, headers=admin)
    assert r.status_code == 200 and r.json()["email"] == "o@ex.com"
    login(client, "o@ex.com", "olga12345")


def test_deleted_user_token_stops_working(client, admin):
    r = client.post(f"{API}/users", json={"username": "temp", "password": "temp12345",
                                         "email": "temp@example.com"}, headers=admin)
    headers = login(client, "temp@example.com", "temp12345")
    client.delete(f"{API}/users/{r.json()['id']}", headers=admin)
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


# ---------- Валидация ----------


def test_amount_validation(client, admin):
    for bad in ["-5", "0", "abc", "10.123"]:
        r = client.post(
            f"{API}/recurring-payments",
            json={
                "name": "x",
                "amount": bad,
                "currency": "RUB",
                "first_due_date": "2026-11-01",
            },
            headers=admin,
        )
        assert r.status_code == 422, bad
    r = client.post(
        f"{API}/recurring-payments",
        json={
            "name": "x",
            "amount": "5",
            "currency": "GBP",
            "first_due_date": "2026-11-01",
        },
        headers=admin,
    )
    assert r.status_code == 422


def test_error_format_matches_frontend_contract(client, admin):
    r = client.post(
        f"{API}/recurring-payments",
        json={"name": "x", "amount": "-1", "currency": "GBP"},
        headers=admin,
    )
    body = r.json()
    assert r.status_code == 422
    assert body["code"] == 422 and body["status"] == "Unprocessable Entity"
    assert body["message"] == "Сумма должна быть больше нуля"

    r = client.get(f"{API}/users", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and r.json()["message"] == "Недействительный токен"
