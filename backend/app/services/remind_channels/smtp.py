import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings
from app.logging_config import get_logger
from app.models import PaymentOccurrence
from app.services.remind_channels.utils import format_amount, get_time_until

logger = get_logger(__name__)

# В почте inline-кнопок нет — reply_markup игнорируем
supports_reply_markup = False


def ready_to_send() -> bool:
    # Логин на почтовом сервере — это сам адрес ящика (SMTP_ADDR),
    # отдельного SMTP_USER у нас нет.
    return bool(
        settings.smtp_host
        and settings.smtp_addr
        and settings.smtp_password.get_secret_value()
    )


def build_message(occ: PaymentOccurrence, on: date) -> str:
    when = get_time_until(occ.due_date, on)
    # Возвращаем HTML для красивого отображения в почте
    return (
        "<h3>🔔 Напоминание об оплате</h3>"
        f"<p><b>{occ.name}</b></p>"
        f"<p>Сумма: <b>{format_amount(occ.amount, occ.currency)}</b></p>"
        f"<p>Дата оплаты: <b>{occ.due_date.strftime('%d.%m.%Y')}</b> ({when})</p>"
    )


def _send_message_to(email: str, text: str) -> None:
    """Отправляет одно письмо одному адресату."""
    if not settings.smtp_addr:
        raise RuntimeError("SMTP_ADDR не задан — некуда отправлять письма")

    msg = EmailMessage()
    msg["Subject"] = settings.smtp_subject
    msg["From"] = formataddr((settings.smtp_name, str(settings.smtp_addr)))
    msg["To"] = email

    # Добавляем plain-text fallback и HTML-версию
    msg.set_content("Для просмотра письма используйте клиент с поддержкой HTML.")
    msg.add_alternative(text, subtype="html")

    password = settings.smtp_password.get_secret_value()
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        settings.smtp_host, settings.smtp_port, context=context, timeout=15
    ) as server:
        server.login(str(settings.smtp_addr), password)
        server.send_message(msg)


def send_message(
    text: str,
    reply_markup: dict | None = None,
    recipients: list[str] | None = None,
) -> int:
    """Рассылает письмо всем получателям — по одному письму на адрес.

    Получателей (адреса из базы) передаёт вызывающий: так правило «кому
    писать» живёт в одном месте, а канал только отправляет.

    Возвращает, сколько писем доставлено. Ноль означает «никому не доставлено» —
    это не успех: вызывающий не должен считать период отправленным.
    """
    if not recipients:
        logger.warning("Нет получателей с email — письмо не отправлено")
        return 0

    sent = 0
    failed: list[str] = []
    for address in recipients:
        try:
            _send_message_to(address, text)
            sent += 1
        except Exception:
            failed.append(address)
            # logger.exception сам добавляет трассировку — текст ошибки в нём лишний
            logger.exception(f"Не удалось отправить письмо на {address}")

    logger.info(
        f"Письмо отправлено {sent} из {len(recipients)} получателей"
        + (f"; не доставлено: {', '.join(failed)}" if failed else "")
    )
    return sent
