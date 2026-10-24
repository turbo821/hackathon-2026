import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings
from app.models import PaymentOccurrence
from app.services.remind_channels.utils import format_amount, get_time_until

def ready_to_send() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password.get_secret_value())

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
    msg["From"] = formataddr((settings.smtp_name, settings.smtp_addr))
    msg["To"] = email
    
    # Добавляем plain-text fallback и HTML-версию
    msg.set_content("Для просмотра письма используйте клиент с поддержкой HTML.")
    msg.add_alternative(text, subtype="html")

    password = settings.smtp_password.get_secret_value()
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as server:
        server.login(settings.smtp_user, password)
        server.send_message(msg)

def send_message(text: str) -> None:
    # TODO: отправить сообщение всем пользователям используя _send_message_to
    pass