"""
Telegram long polling bot — запускает бесконечный цикл обработки сообщений.

Бот постоянно слушает входящие сообщения от Telegram и мгновенно
отвечает на команду /start.

Использование:
    python manage.py telegram_polling

Для работы в фоне:
    nohup python manage.py telegram_polling > telegram_bot.log 2>&1 &
    # или через systemd
"""

import time
import logging
import json
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from django.core.management.base import BaseCommand
from django.conf import settings
from students.telegram_bot import process_single_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает Telegram бота в режиме long polling (постоянно слушает сообщения)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=2,
            help='Интервал между запросами в секундах (по умолчанию: 2)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Таймаут long polling в секундах (по умолчанию: 30)',
        )

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            self.stdout.write(self.style.ERROR('TELEGRAM_BOT_TOKEN not configured!'))
            return

        poll_interval = options['interval']
        poll_timeout = options['timeout']
        offset = 0

        self.stdout.write(self.style.SUCCESS(
            '🤖 Telegram бот запущен в режиме long polling\n'
            f'   Интервал: {poll_interval}с, Таймаут: {poll_timeout}с\n'
            '   Ожидаю сообщения... (Ctrl+C для остановки)'
        ))

        while True:
            try:
                offset = self._poll_updates(token, offset, poll_timeout)
                time.sleep(poll_interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n🛑 Бот остановлен.'))
                break
            except Exception as e:
                logger.error(f'Unexpected error in polling loop: {e}')
                self.stdout.write(self.style.ERROR(f'Ошибка: {e}. Повтор через 5 секунд...'))
                time.sleep(5)

    def _poll_updates(self, token, offset, timeout):
        """Один цикл polling — получает и обрабатывает обновления."""
        url = (
            f'https://api.telegram.org/bot{token}/getUpdates'
            f'?offset={offset}'
            f'&timeout={timeout}'
            f'&allowed_updates=["message","my_chat_member"]'
        )

        req = urllib_request.Request(url)

        try:
            with urllib_request.urlopen(req, timeout=timeout + 5) as response:
                data = json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            logger.error(f'Telegram API error: {error_body}')
            return offset
        except URLError as e:
            logger.error(f'Network error: {e}')
            return offset
        except Exception as e:
            logger.error(f'Failed to get updates: {e}')
            return offset

        if not data.get('ok'):
            logger.error('Telegram API error: %s', data.get('description'))
            return offset

        for update in data.get('result', []):
            update_id = update.get('update_id', 0)
            if update_id >= offset:
                offset = update_id + 1

            try:
                process_single_update(update)
            except Exception as e:
                logger.error(f'Error processing update {update_id}: {e}')

        return offset