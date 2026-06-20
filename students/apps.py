import logging
import os
from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class StudentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'students'
    verbose_name = 'Ученики и преподаватели'
    
    def ready(self):
        """
        Автоматически синхронизирует Telegram chat_id при запуске сервера.
        Запускается только если:
        - TELEGRAM_BOT_TOKEN задан
        - Не в режиме миграций (manage.py migrate/makemigrations)
        - Не в режиме shell/check
        """
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        
        # Проверяем, что это не manage.py migrate/makemigrations/check/shell
        import sys
        if len(sys.argv) > 1 and sys.argv[1] in (
            'migrate', 'makemigrations', 'check', 'shell', 'test',
            'collectstatic', 'compilemessages', 'makemessages',
        ):
            return
        
        # Запускаем синхронизацию в фоне, чтобы не замедлять запуск
        try:
            from .telegram_bot import sync_telegram_chat_ids
            # Используем threading, чтобы не блокировать запуск сервера
            import threading
            thread = threading.Thread(target=sync_telegram_chat_ids, daemon=True)
            thread.start()
            logger.info('Telegram chat_id sync started in background')
        except Exception as e:
            logger.error(f'Failed to start Telegram chat_id sync: {e}')