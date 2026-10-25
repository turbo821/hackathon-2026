import smtplib
import socket
import ssl
import struct
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlparse

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


<<<<<<< HEAD
def _recv_exact(sock: socket.socket, size: int) -> bytes:
    """Читает ровно size байт — recv() может вернуть меньше."""
    chunks = []
    while size > 0:
        chunk = sock.recv(size)
        if not chunk:
            raise smtplib.SMTPServerDisconnected("SOCKS5-прокси закрыл соединение")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def _socks5_connect(proxy_url: str, host: str, port: int) -> socket.socket:
    """Открывает TCP-соединение до host:port через SOCKS5-прокси.

    smtplib прокси не умеет, поэтому руками: приветствие, CONNECT с именем
    домена (не IP — иначе TLS-проверка сертификата увидит адрес вместо имени).
    """
    parsed = urlparse(proxy_url)
    proxy_host = parsed.hostname
    proxy_port = parsed.port or 1080
    if not proxy_host:
        raise ValueError(f"Некорректный адрес прокси: {proxy_url}")

    sock = socket.create_connection((proxy_host, proxy_port), timeout=30)
    sock.settimeout(30)
    try:
        # Приветствие: версия 5, единственный метод — без авторизации.
        sock.sendall(b"\x05\x01\x00")
        reply = _recv_exact(sock, 2)
        if reply[0] != 5 or reply[1] != 0:
            raise smtplib.SMTPServerDisconnected(
                f"SOCKS5-прокси не согласовался: {reply!r}"
            )

        # CONNECT: ATYP=3 — имя домена, чтобы TLS знал настоящее имя сервера.
        target = host.encode("idna")
        sock.sendall(
            b"\x05\x01\x00\x03"
            + bytes([len(target)])
            + target
            + struct.pack(">H", port)
        )
        response = _recv_exact(sock, 4)
        if response[1] != 0:
            raise smtplib.SMTPServerDisconnected(
                f"SOCKS5-прокси отказал в соединении (код {response[1]})"
            )
        # Остаток ответа: bound address и порт — читаем и выбрасываем.
        atyp = response[3]
        if atyp == 1:
            _recv_exact(sock, 4)
        elif atyp == 3:
            _recv_exact(sock, _recv_exact(sock, 1)[0])
        elif atyp == 4:
            _recv_exact(sock, 16)
        _recv_exact(sock, 2)
        return sock
    except Exception:
        sock.close()
        raise


def _connect() -> smtplib.SMTP:
    """Открывает соединение с почтовым сервером и логинится.

    Три режима:
    - напрямую с TLS на 465 (обычный случай);
    - напрямую с STARTTLS на 587 — у Mail.ru на 465 отказывает;
    - через SOCKS5-прокси (SMTP_PROXY) — когда до сервера не достучаться.
=======
def _connect() -> smtplib.SMTP:
    """Открывает соединение с почтовым сервером и логинится.

    Два режима:
    - напрямую с TLS на 465 (обычный случай);
    - напрямую с STARTTLS на 587 — у Mail.ru на 465 отказывает.
>>>>>>> 41254a22ffb451ae5892969791cec17148fb0b81
    """
    context = ssl.create_default_context()
    host = settings.smtp_host
    port = settings.smtp_port
    password = settings.smtp_password.get_secret_value()

<<<<<<< HEAD
    if settings.smtp_proxy:
        # smtplib сам прокси не умеет: поднимаем сокет через SOCKS5 руками
        # и отдаём smtplib готовый сокет.
        raw = _socks5_connect(settings.smtp_proxy, host, port)
        server = smtplib.SMTP(timeout=30)
        server.sock = raw
        server.file = raw.makefile("rb", encoding="ascii")
        # starttls() берёт имя сервера из приватного _host: без него TLS
        # проверит сертификат по пустому имени. Публичного параметра нет.
        server._host = host  # type: ignore[attr-defined]
        server.getreply()
        server.ehlo()
        if settings.smtp_starttls:
            server.starttls(context=context)
            server.ehlo()
    elif settings.smtp_starttls:
=======
    if settings.smtp_starttls:
>>>>>>> 41254a22ffb451ae5892969791cec17148fb0b81
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=30)

    server.login(str(settings.smtp_addr), password)
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
