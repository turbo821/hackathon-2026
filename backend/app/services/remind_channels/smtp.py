import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr

from pydantic import EmailStr

from app.config import settings
from app.models import PaymentOccurrence
from app.services.remind_channels.utils import format_amount, get_time_until

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


def _send_message_to(email: EmailStr, text: str) -> None:
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


def send_message(text: str, reply_markup: dict | None = None) -> None:
    # TODO: отправить сообщение всем пользователям используя _send_message_to
    # Пока рассылка не дописана — падаем явно, чтобы период не считать
    # отправленным и попробовать снова позже.
    raise NotImplementedError("SMTP-рассылка ещё не дописана")
