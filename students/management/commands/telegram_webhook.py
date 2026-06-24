"""
Management command to set or unset Telegram bot webhook.

Использование:
    python manage.py telegram_webhook --set https://mathphysedu.ru/students/telegram/webhook/
    python manage.py telegram_webhook --unset
    python manage.py telegram_webhook --info
"""

import json
import logging
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Управление webhook Telegram бота'

    def add_arguments(self, parser):
        parser.add_argument(
            '--set',
            type=str,
            default=None,
            help='Установить webhook URL (например, https://mathphysedu.ru/students/telegram/webhook/)',
        )
        parser.add_argument(
            '--unset',
            action='store_true',
            default=False,
            help='Удалить webhook (переключиться на polling)',
        )
        parser.add_argument(
            '--info',
            action='store_true',
            default=False,
            help='Показать информацию о текущем webhook',
        )

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            raise CommandError('TELEGRAM_BOT_TOKEN not configured in settings')

        if options.get('set'):
            self._set_webhook(token, options['set'])
        elif options.get('unset'):
            self._unset_webhook(token)
        elif options.get('info'):
            self._webhook_info(token)
        else:
            self.stdout.write(self.style.WARNING(
                'Укажите --set URL, --unset или --info\n'
                'Пример: python manage.py telegram_webhook --set https://mathphysedu.ru/students/telegram/webhook/'
            ))

    def _set_webhook(self, token, url):
        """Устанавливает webhook."""
        self.stdout.write(f'Устанавливаю webhook: {url}')

        api_url = f'https://api.telegram.org/bot{token}/setWebhook'
        payload = json.dumps({
            'url': url,
            'allowed_updates': ['message', 'my_chat_member'],
        }).encode('utf-8')

        req = urllib_request.Request(
            api_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    self.stdout.write(self.style.SUCCESS(
                        f'Webhook успешно установлен на {url}'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Ошибка Telegram API: {result.get("description", "Unknown error")}'
                    ))
        except (URLError, HTTPError) as e:
            raise CommandError(f'Не удалось установить webhook: {e}')

    def _unset_webhook(self, token):
        """Удаляет webhook (возвращает polling)."""
        self.stdout.write('Удаляю webhook...')

        api_url = f'https://api.telegram.org/bot{token}/deleteWebhook'
        req = urllib_request.Request(api_url, method='POST')

        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    self.stdout.write(self.style.SUCCESS(
                        'Webhook успешно удалён. Бот переключён на polling.'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Ошибка Telegram API: {result.get("description", "Unknown error")}'
                    ))
        except (URLError, HTTPError) as e:
            raise CommandError(f'Не удалось удалить webhook: {e}')

    def _webhook_info(self, token):
        """Показывает информацию о текущем webhook."""
        api_url = f'https://api.telegram.org/bot{token}/getWebhookInfo'
        req = urllib_request.Request(api_url)

        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    info = result['result']
                    self.stdout.write('=== Информация о webhook ===')
                    self.stdout.write(f'URL:           {info.get("url", "(не установлен)")}')
                    self.stdout.write(f'Ошибок:        {info.get("failed_count", 0)}')
                    self.stdout.write(f'Макс. кол-во:  {info.get("max_connections", 40)}')
                    self.stdout.write(f'Обновлений:    {info.get("pending_update_count", 0)}')
                    last_error = info.get('last_error_message')
                    if last_error:
                        self.stdout.write(self.style.ERROR(f'Последняя ошибка: {last_error}'))
                    last_error_date = info.get('last_error_date')
                    if last_error_date:
                        from datetime import datetime
                        self.stdout.write(
                            f'Дата ошибки:   {datetime.fromtimestamp(last_error_date)}'
                        )
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Ошибка Telegram API: {result.get("description", "Unknown error")}'
                    ))
        except (URLError, HTTPError) as e:
            raise CommandError(f'Не удалось получить информацию о webhook: {e}')