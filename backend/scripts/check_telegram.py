"""Проверка настроек Telegram: токен, чат, прокси, отправка тестового сообщения.

Запуск из папки backend/:

    python -m scripts.check_telegram                    # только проверки, без отправки
    python -m scripts.check_telegram --send             # + тестовое сообщение в чат
    python -m scripts.check_telegram --send --chat -100… # в другой чат

Код возврата: 0 — всё в порядке, 1 — есть проблема.

Зачем скрипт: бот работает в фоне и при ошибке молчит — из логов воркера видно
только «Telegram не отвечает». Скрипт проверяет тот же путь, что и приложение
(тот же токен, тот же чат, тот же прокси), и говорит, где именно сломалось:
токен неверный, чат недоступен, прокси не отвечает или Telegram отклонил.
"""

import argparse
import logging
import os
import sys

from app.config import settings
from app.logging_config import log_event, setup_logging
from app.services import telegram

logger = logging.getLogger("scripts.check_telegram")

REPORT_SEPARATOR = "=" * 60


def check_config() -> list[str]:
    """Проверяет настройки без обращения к Telegram."""
    problems: list[str] = []

    token = settings.telegram_bot_token
    if not token:
        problems.append("TELEGRAM_BOT_TOKEN не задан")
    elif ":" not in token:
        problems.append(
            "TELEGRAM_BOT_TOKEN выглядит не как токен (ожидается «<число>:<секрет>») — "
            "возможно, скопирован только секрет или строка обрезалась"
        )

    if not settings.telegram_chat_id:
        problems.append(
            "TELEGRAM_CHAT_ID не задан — напоминания отправлять некуда. "
            "Узнать id чата можно у @userinfobot"
        )

    if not settings.telegram_bot_username:
        problems.append(
            "TELEGRAM_BOT_USERNAME не задан — скрипт узнает его у Telegram "
            "при первом обращении, но лучше задать явно"
        )

    return problems


def check_bot() -> tuple[bool, str]:
    """Спрашивает у Telegram, кто этот бот (getMe)."""
    try:
        me = telegram.get_me()
    except telegram.TelegramNotConfigured as e:
        return False, str(e)
    except telegram.TelegramError as e:
        return False, str(e)
    except Exception as e:  # сеть, прокси, таймаут
        return False, f"не удалось обратиться к Telegram: {type(e).__name__}: {e}"

    username = me.get("username") or "?"
    return True, f"@{username} (id={me.get('id')})"


def check_chat(chat_id: str) -> tuple[bool, str]:
    """Проверяет, что чат существует и бот может в него писать."""
    try:
        telegram._call("getChat", {"chat_id": chat_id})
    except telegram.TelegramError as e:
        return False, str(e)
    except Exception as e:
        return False, f"не удалось обратиться к Telegram: {type(e).__name__}: {e}"
    return True, "чат доступен боту"


def send_test(chat_id: str) -> tuple[bool, str]:
    """Отправляет тестовое сообщение рабочим кодом приложения."""
    try:
        telegram.send_message(
            "<b>Проверка Telegram</b>\n\nТестовое сообщение. Если вы его видите — "
            "настройки рабочие.",
            chat_id=chat_id,
        )
    except telegram.TelegramNotConfigured as e:
        return False, str(e)
    except telegram.TelegramError as e:
        return False, str(e)
    except Exception as e:
        return False, f"не удалось отправить: {type(e).__name__}: {e}"
    return True, "сообщение отправлено"


def main() -> int:
    setup_logging(name="check_telegram")
    parser = argparse.ArgumentParser(
        description="Проверка настроек Telegram (токен, чат, прокси, отправка)"
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="отправить тестовое сообщение в чат",
    )
    parser.add_argument(
        "--chat",
        metavar="CHAT_ID",
        help="id чата для проверки (по умолчанию TELEGRAM_CHAT_ID из .env)",
    )
    args = parser.parse_args()

    chat_id = args.chat or settings.telegram_chat_id

    print(REPORT_SEPARATOR)
    print("Отчёт проверки Telegram")
    print(REPORT_SEPARATOR)
    print("Настройки Telegram:")
    print(f"  токен:    {'задан' if settings.telegram_bot_token else 'НЕ ЗАДАН'}")
    print(f"  чат:      {chat_id or 'НЕ ЗАДАН'}")
    print(f"  username: {settings.telegram_bot_username or 'не задан'}")
    print(f"  прокси:   {os.getenv('BOT_PROXY_URL') or 'не задан'}")
    print()

    problems = check_config()
    if problems:
        print("Проблемы в настройках:")
        for item in problems:
            print(f"  - {item}")
            log_event(logger, logging.ERROR, "telegram.config_invalid", reason=item)
        print()

    ok, message = check_bot()
    print(f"Бот: {'OK' if ok else 'FAIL'} — {message}")
    log_event(
        logger,
        logging.INFO if ok else logging.ERROR,
        "telegram.get_me",
        ok=ok,
        detail=message,
    )

    if ok and chat_id:
        chat_ok, chat_message = check_chat(chat_id)
        print(f"Чат: {'OK' if chat_ok else 'FAIL'} — {chat_message}")
        log_event(
            logger,
            logging.INFO if chat_ok else logging.ERROR,
            "telegram.chat_check",
            ok=chat_ok,
            chat_id=chat_id,
            detail=chat_message,
        )

        if args.send:
            sent, sent_message = send_test(chat_id)
            print(f"Тестовое сообщение: {'OK' if sent else 'FAIL'} — {sent_message}")
            log_event(
                logger,
                logging.INFO if sent else logging.ERROR,
                "telegram.test_sent",
                ok=sent,
                chat_id=chat_id,
                detail=sent_message,
            )
            ok = ok and chat_ok and sent

    if not ok or problems:
        print()
        print("Что делать:")
        print("  1. Токен взять у @BotFather (команда /newbot или /token).")
        print("  2. Id чата узнать у @userinfobot, бот должен быть в этом чате.")
        print("  3. Если чат — группа, бот должен быть её администратором.")
        print(
            "  4. Если включён прокси — проверить его: curl -x socks5h://<прокси> https://api.telegram.org"
        )
        print("  5. Перезапустить воркер: docker compose restart worker")
        return 1

    print()
    print("Настройки Telegram выглядят рабочими.")
    if not args.send:
        print("Отправить тестовое сообщение: python -m scripts.check_telegram --send")
    return 0


if __name__ == "__main__":
    sys.exit(main())
