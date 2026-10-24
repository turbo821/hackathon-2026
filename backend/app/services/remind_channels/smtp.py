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


def _build_message(text: str) -> EmailMessage:
    """Собирает одно письмо для пачки получателей.

    В заголовке To — undisclosed-recipients: адреса других получателей не
    должны светиться в чужих письмах. В конверте письма (RCPT TO) они всё
    равно будут — их подставляет sendmail.
    """
    msg = EmailMessage()
    msg["Subject"] = settings.smtp_subject
    msg["From"] = formataddr((settings.smtp_name, str(settings.smtp_addr)))
    msg["To"] = "undisclosed-recipients:;"

    msg.set_content("Для просмотра письма используйте клиент с поддержкой HTML.")
    msg.add_alternative(text, subtype="html")
    return msg


def _connect() -> smtplib.SMTP_SSL:
    """Открывает соединение с почтовым сервером и логинится."""
    context = ssl.create_default_context()
    server = smtplib.SMTP_SSL(
        settings.smtp_host, settings.smtp_port, context=context, timeout=30
    )
    server.login(str(settings.smtp_addr), settings.smtp_password.get_secret_value())
    return server


def send_message(
    text: str,
    reply_markup: dict | None = None,
    recipients: list[str] | None = None,
) -> int:
    """Рассылает письмо пачкой: одно соединение, одно письмо на всех.

    Получателей (адреса из базы) передаёт вызывающий: так правило «кому
    писать» живёт в одном месте, а канал только отправляет.

    Возвращает, сколько писем доставлено. Ноль означает «никому не доставлено» —
    это не успех: вызывающий не должен считать период отправленным.
    """
    if not recipients:
        logger.warning("Нет получателей с email — письмо не отправлено")
        return 0

    if not settings.smtp_addr:
        raise RuntimeError("SMTP_ADDR не задан — некуда отправлять письма")

    # sendmail сам делает всю пачку: один MAIL FROM, по RCPT TO на каждого
    # получателя и один DATA. Соединение и вход — тоже одни на всю рассылку,
    # поэтому лимиты почтового сервера не растут вместе с числом получателей.
    try:
        with _connect() as server:
            refused = server.sendmail(
                str(settings.smtp_addr),
                recipients,
                # as_bytes обязателен: sendmail кодирует str как ASCII,
                # а в письме есть кириллица.
                _build_message(text).as_bytes(),
            )
    except smtplib.SMTPRecipientsRefused as e:
        # Часть адресов сервер не принял — остальные письмо получили.
        # sendmail бросает это исключение и когда отказали все.
        refused = e.recipients
    except smtplib.SMTPException:
        logger.exception("Письмо не отправлено")
        return 0

    failed = list(refused)
    delivered = len(recipients) - len(failed)
    logger.info(
        f"Письмо отправлено {delivered} из {len(recipients)} получателей"
        + (f"; не доставлено: {', '.join(failed)}" if failed else "")
    )
    return delivered
