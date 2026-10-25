"""Подключение к почте через SOCKS5-прокси.

smtplib прокси не умеет, поэтому CONNECT руками: проверяем, что запрос
уходит в прокси правильным байтам и что дальше всё идёт как обычно.
"""

import smtplib
import socket
import struct
import threading

import pytest
from app.services.remind_channels import smtp


class FakeSocks5Server:
    """Подделка SOCKS5: принимает CONNECT и отдаёт «адрес назначения»."""

    def __init__(self, accept: bool = True):
        self.accept = accept
        self.request: bytes = b""
        self.error = None

    def __enter__(self):
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._server.close()
        return False

    def _serve(self):
        try:
            conn, _ = self._server.accept()
        except OSError:
            return
        with conn:
            try:
                conn.recv(2)  # версия и число методов
                conn.recv(3)  # методы
                conn.sendall(b"\x05\x00")  # согласовали «без авторизации»
                head = conn.recv(4)
                if len(head) < 4:
                    return
                # Для домена после заголовка идёт байт длины, потом имя и порт
                length = conn.recv(1)[0]
                host = b""
                while len(host) < length:
                    host += conn.recv(length - len(host))
                port_bytes = b""
                while len(port_bytes) < 2:
                    port_bytes += conn.recv(2 - len(port_bytes))
                self.request = head + bytes([length]) + host + port_bytes
                if self.accept:
                    conn.sendall(b"\x05\x00\x00\x01" + b"\x00" * 4 + b"\x00\x00")
                else:
                    conn.sendall(b"\x05\x05\x00\x01" + b"\x00" * 4 + b"\x00\x00")
                conn.recv(10)
            except OSError:
                pass


def test_socks5_connect_sends_domain_not_ip():
    """В CONNECT должно уйти имя домена: иначе TLS не проверит сертификат."""
    with FakeSocks5Server() as proxy:
        sock = smtp._socks5_connect(
            f"socks5://127.0.0.1:{proxy.port}", "smtp.mail.ru", 587
        )
        sock.close()

    assert b"smtp.mail.ru" in proxy.request
    assert proxy.request.endswith(struct.pack(">H", 587))
    # ATYP=3 — домен, а не IP
    assert proxy.request[3] == 3
    # после ATYP идёт длина имени, затем само имя
    assert proxy.request[4] == len("smtp.mail.ru")


def test_socks5_connect_reports_refusal():
    """Прокси может отказать — об этом надо узнать, а не молча получить обрыв."""
    with FakeSocks5Server(accept=False) as proxy:
        with pytest.raises(smtplib.SMTPServerDisconnected):
            smtp._socks5_connect(
                f"socks5://127.0.0.1:{proxy.port}", "smtp.mail.ru", 587
            )


def test_connect_uses_proxy_and_starttls(monkeypatch):
    """С прокси и STARTTLS: поднимаем сокет, говорим EHLO и включаем TLS."""
    events = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            events.append(("init", args, kwargs))
            self.sock = None
            self.file = None
            self._host = ""
            self._encoding = "ascii"

        def getreply(self):
            return 220, b"ready"

        def ehlo(self):
            events.append(("ehlo",))
            return 250, b"ok"

        def starttls(self, context=None):
            events.append(("starttls",))
            return 220, b"ok"

        def login(self, user, password):
            events.append(("login", user))
            return 235, b"ok"

    class FakeRaw:
        def __init__(self):
            self.closed = False

        def makefile(self, mode, encoding=None):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(smtp.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtp, "_socks5_connect", lambda *a: FakeRaw())
    monkeypatch.setattr(smtp.settings, "smtp_proxy", "socks5://127.0.0.1:1080")
    monkeypatch.setattr(smtp.settings, "smtp_starttls", True)

    smtp._connect()

    kinds = [e[0] for e in events]
    assert kinds == ["init", "ehlo", "starttls", "ehlo", "login"]
    # TLS-проверка сертификата идёт по имени, а не по адресу
    assert events[0][2].get("timeout") == 30


def test_connect_direct_starttls(monkeypatch):
    """Без прокси, но с STARTTLS — обычный путь через smtplib."""
    events = []

    class FakeSMTP:
        def __init__(self, host=None, port=None, timeout=None):
            events.append(("init", host, port))
            self._host = host or ""

        def ehlo(self):
            events.append(("ehlo",))
            return 250, b"ok"

        def starttls(self, context=None):
            events.append(("starttls",))
            return 220, b"ok"

        def login(self, user, password):
            events.append(("login", user))
            return 235, b"ok"

    monkeypatch.setattr(smtp.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtp.settings, "smtp_proxy", "")
    monkeypatch.setattr(smtp.settings, "smtp_starttls", True)

    smtp._connect()

    kinds = [e[0] for e in events]
    assert kinds == ["init", "ehlo", "starttls", "ehlo", "login"]
