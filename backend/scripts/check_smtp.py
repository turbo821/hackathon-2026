"""Проверка настроек SMTP: подключение, вход и (по желанию) тестовое письмо.

Запуск из папки backend/:

    python -m scripts.check_smtp                 # только проверка, письмо не отправляется
    python -m scripts.check_smtp --to me@example.com   # + тестовое письмо на адрес

Код возврата: 0 — всё в порядке, 1 — есть проблема.

Скрипт проверяет ровно то, что делает приложение: тот же хост, порт, TLS и
логин, что в app/services/remind_channels/smtp.py. Поэтому если здесь вход
проходит — значит рабочий код тоже сможет отправить письмо.
"""

import argparse
import smtplib
import ssl
import sys

from app.config import settings


def _mask(value: str) -> str:
    """Показывает значение, но не выдаёт секрет целиком."""
    if not value:
        return "(пусто)"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}…{value[-2:]}"


def check_config() -> list[str]:
    """Проверяет сами настройки. Возвращает список проблем."""
    problems: list[str] = []

    if not settings.smtp_host:
        problems.append("SMTP_HOST не задан")
    if not settings.smtp_addr:
        problems.append(
            "SMTP_ADDR не задан — это и адрес отправителя, и логин. "
            "Укажите в .env свой ящик"
        )
    elif str(settings.smtp_addr).lower() in ("you@example.com", "admin@example.com"):
        problems.append(
            f"SMTP_ADDR={settings.smtp_addr} — это плейсхолдер, а не ваш ящик"
        )
    if not settings.smtp_password.get_secret_value():
        problems.append("SMTP_PASSWORD не задан")
    if not settings.smtp_name:
        problems.append("SMTP_NAME не задан — письма придут без имени отправителя")

    # 465 — неявный SSL (SMTP_SSL), 587 — STARTTLS. Приложение использует
    # SMTP_SSL, поэтому на 587 вход не пройдёт.
    if settings.smtp_port == 587:
        problems.append(
            "SMTP_PORT=587 требует STARTTLS, а приложение подключается через "
            "SMTP_SSL (465). Поставьте 465 или допишите starttls в smtp.py"
        )
    elif settings.smtp_port != 465:
        problems.append(
            f"SMTP_PORT={settings.smtp_port} — приложение ждёт 465 (SMTP_SSL)"
        )

    return problems


def check_connection() -> tuple[bool, str]:
    """Подключается и входит. Возвращает (успех, описание)."""
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            context=context,
            timeout=15,
        ) as server:
            code, banner = server.ehlo()
            if code != 250:
                return False, f"сервер отклонил EHLO: код {code}"
            server_name = banner.decode(errors="replace").splitlines()[0]

            try:
                server.login(
                    str(settings.smtp_addr), settings.smtp_password.get_secret_value()
                )
            except smtplib.SMTPAuthenticationError as e:
                return (
                    False,
                    f"не прошёл вход ({e.smtp_code}): неверный адрес или пароль. "
                    f"Логин — это SMTP_ADDR ({_mask(str(settings.smtp_addr))}), "
                    f"для Mail.ru это полный адрес ящика с паролем приложения, "
                    f"а не основного пароля от почты",
                )
            except smtplib.SMTPException as e:
                return False, f"ошибка SMTP: {type(e).__name__}: {e}"

            return True, f"{server_name} — вход выполнен"
    except ssl.SSLCertVerificationError as e:
        return False, f"не прошла проверка TLS-сертификата: {e}"
    except (smtplib.SMTPException, OSError) as e:
        return False, f"не удалось подключиться: {type(e).__name__}: {e}"


def send_test(addresses: list[str]) -> tuple[bool, str]:
    """Отправляет тестовое письмо рабочим кодом приложения — по одному на адрес."""
    try:
        from app.services.remind_channels.smtp import send_message

        delivered = send_message(
            "<h3>Проверка SMTP</h3><p>Тестовое письмо. Если вы его видите — настройки рабочие.</p>",
            recipients=addresses,
        )
        if not delivered:
            return False, f"доставлено 0 из {len(addresses)}"
        return True, f"доставлено {delivered} из {len(addresses)}"
    except Exception as e:
        return False, f"не удалось отправить: {type(e).__name__}: {e}"


def show_recipients() -> None:
    """Показывает, кому пойдут реальные напоминания."""
    try:
        from app.db import SessionLocal
        from app.services.recipients import email_recipients

        db = SessionLocal()
        try:
            recipients = email_recipients(db)
        finally:
            db.close()
    except Exception as e:
        print(f"Получатели: не удалось прочитать базу ({type(e).__name__}: {e})")
        return

    if recipients:
        print("Получатели напоминаний из базы:")
        for address in recipients:
            print(f"  - {address}")
    else:
        print("Получатели напоминаний из базы: пусто — письма уходить некому")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверка настроек SMTP (подключение, вход, тестовое письмо)"
    )
    parser.add_argument(
        "--to",
        metavar="ADDRESS",
        nargs="+",
        help=(
            "адреса, куда отправить тестовое письмо — по одному письму на адрес, "
            "как в реальной рассылке (по умолчанию письма не отправляются)"
        ),
    )
    args = parser.parse_args()

    print("Настройки SMTP:")
    print(f"  хост:      {settings.smtp_host}:{settings.smtp_port}")
    print(f"  адрес:     {settings.smtp_addr} (логин на сервере)")
    print(f"  пароль:    {_mask(settings.smtp_password.get_secret_value())}")
    print(f"  имя:       {settings.smtp_name}")
    print(f"  тема:      {settings.smtp_subject}")
    print()

    problems = check_config()
    if problems:
        print("Проблемы в настройках:")
        for item in problems:
            print(f"  - {item}")
        print()

    ok, message = check_connection()
    print(f"Подключение: {'OK' if ok else 'FAIL'} — {message}")

    show_recipients()

    if ok and args.to:
        sent, send_message = send_test(args.to)
        print(f"Тестовые письма: {'OK' if sent else 'FAIL'} — {send_message}")

    if not ok or problems:
        print()
        print("Что делать:")
        print(
            "  1. Укажите реальный ящик в SMTP_ADDR (не плейсхолдер you@example.com)."
        )
        print("  2. Укажите в SMTP_PASSWORD пароль приложения ящика, а не от почты.")
        print("  3. Убедитесь, что порт 465 (SMTP_SSL).")
        print("  4. Перезапустите воркер: docker compose restart worker")
        return 1

    print()
    print("Настройки SMTP выглядят рабочими.")
    if not args.to:
        print(
            "Отправить тестовое письмо: python -m scripts.check_smtp --to <адрес>\n"
            "Проверить массовую рассылку: python -m scripts.check_smtp --to <адрес1> <адрес2> ..."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
