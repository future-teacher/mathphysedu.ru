#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальный dev-сервер с HTTPS для Django.

Проблема: браузер (HSTS, расширение или вручную набранный адрес)
принудительно открывает https://127.0.0.1:8000/, а `manage.py runserver`
умеет только HTTP. Отсюда ошибки:
    "You're accessing the development server over HTTPS, but it only supports HTTP."
    "code 400, message Bad request version ('\\x06\\x04\\x03...')"  # TLS-рукопожатие

Решение: скрипт поднимает Django на 127.0.0.1:8001 (HTTP) и TLS-прокси
на 127.0.0.1:8000 (HTTPS) с самоподписанным сертификатом. Сайт открывается
по https://127.0.0.1:8000/ (в браузере нужно один раз подтвердить
самоподписанный сертификат).

Запуск:
    python3 dev_https.py
    python3 dev_https.py --port 8443        # другой внешний HTTPS-порт
    python3 dev_https.py --http-port 8002   # другой внутренний HTTP-порт

Остановка: Ctrl+C
"""

import argparse
import os
import signal
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CERT_DIR = BASE_DIR / '.devcerts'
CERT_FILE = CERT_DIR / 'cert.pem'
KEY_FILE = CERT_DIR / 'key.pem'

DEFAULT_HTTPS_PORT = 8000
DEFAULT_HTTP_PORT = 8001


def ensure_cert() -> None:
    """Создаёт самоподписанный сертификат для localhost/127.0.0.1."""
    CERT_DIR.mkdir(exist_ok=True)
    if CERT_FILE.exists() and KEY_FILE.exists():
        return
    subprocess.run(
        [
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', str(KEY_FILE), '-out', str(CERT_FILE),
            '-days', '365', '-nodes',
            '-subj', '/CN=127.0.0.1',
            '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
        ],
        check=True,
        capture_output=True,
    )
    print(f'🔐 Самоподписанный сертификат создан: {CERT_FILE}')


def start_django(http_port: int) -> subprocess.Popen:
    """Запускает manage.py runserver в отдельной группе процессов."""
    return subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{http_port}'],
        cwd=str(BASE_DIR),
        start_new_session=True,
    )


def _pump(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass


def _forward(client: socket.socket, http_port: int) -> None:
    """Пробрасывает трафик между TLS-клиентом и HTTP-сервером Django."""
    upstream = None
    try:
        upstream = socket.create_connection(('127.0.0.1', http_port))
        t1 = threading.Thread(target=_pump, args=(client, upstream), daemon=True)
        t2 = threading.Thread(target=_pump, args=(upstream, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except OSError:
        pass
    finally:
        for s in (client, upstream):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description='Django dev-сервер с HTTPS')
    parser.add_argument(
        '--port', type=int, default=DEFAULT_HTTPS_PORT,
        help=f'внешний HTTPS-порт (по умолчанию {DEFAULT_HTTPS_PORT})',
    )
    parser.add_argument(
        '--http-port', type=int, default=DEFAULT_HTTP_PORT,
        help=f'внутренний HTTP-порт Django (по умолчанию {DEFAULT_HTTP_PORT})',
    )
    args = parser.parse_args()

    ensure_cert()

    # Проверяем, что внешний порт свободен
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(('127.0.0.1', args.port))
    except OSError:
        print(
            f'❌ Порт {args.port} уже занят. Остановите текущий runserver '
            f'(Ctrl+C в его терминале) или запустите с другим портом:\n'
            f'    python3 dev_https.py --port 8443'
        )
        return 1
    finally:
        probe.close()

    django = start_django(args.http_port)
    print(f'▶ Django запущен на http://127.0.0.1:{args.http_port}')

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', args.port))
    server.listen(128)
    print(f'🔒 HTTPS-прокси запущен: https://127.0.0.1:{args.port}/')
    print('   Откройте этот адрес в браузере и подтвердите самоподписанный сертификат.')
    print('   Остановка: Ctrl+C')

    try:
        while True:
            conn, _ = server.accept()
            try:
                tls_conn = ctx.wrap_socket(conn, server_side=True)
            except (ssl.SSLError, OSError):
                conn.close()
                continue
            threading.Thread(
                target=_forward, args=(tls_conn, args.http_port), daemon=True
            ).start()
    except KeyboardInterrupt:
        print('\n⏹ Останавливаю...')
    finally:
        server.close()
        try:
            os.killpg(os.getpgid(django.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        django.wait()
    return 0


if __name__ == '__main__':
    sys.exit(main())