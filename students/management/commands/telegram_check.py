"""
Диагностика Telegram-бота.

Использование:
    python manage.py telegram_check

Проверяет:
1. Наличие TELEGRAM_BOT_TOKEN и доступность бота (getMe)
2. Состояние webhook (установлен ли, ошибки доставки, pending updates)
3. Конфликт режимов: webhook + polling одновременно
4. Статистику подписчиков в БД (TelegramUser, chat_id у Students)
5. Даёт рекомендации, что исправить
"""

import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from students.models import Student, Teacher, TelegramUser
from students.telegram_bot import get_bot_info, get_webhook_info

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Проверяет настройки Telegram-бота: токен, webhook/polling, подписчиков'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== ДИАГНОСТИКА TELEGRAM-БОТА ==='))

        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            self.stderr.write(
                self.style.ERROR(
                    '❌ TELEGRAM_BOT_TOKEN не задан. Проверьте .env на сервере '
                    '(ключ TELEGRAM_BOT_TOKEN).'
                )
            )
            return

        self.stdout.write(
            f'✅ Токен задан (TELEGRAM_BOT_ENABLED={getattr(settings, "TELEGRAM_BOT_ENABLED", False)})'
        )

        # 1. getMe — токен и доступность API
        me = get_bot_info()
        if not me.get('ok'):
            self.stdout.write(
                self.style.ERROR(
                    f"❌ getMe не прошёл: {me.get('description', 'Unknown error')} — "
                    'проверьте TELEGRAM_BOT_TOKEN.'
                )
            )
            return
        bot = me['result']
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Бот доступен: @{bot.get('username')} ({bot.get('first_name')})"
            )
        )
        self.stdout.write(
            f"   Имя в интерфейсе сайта: {getattr(settings, 'TELEGRAM_BOT_USERNAME', '@MathPhyseduBot')}"
        )

        # 2. Webhook vs polling
        wh = get_webhook_info()
        if not wh.get('ok'):
            self.stdout.write(
                self.style.ERROR(
                    f"❌ getWebhookInfo не прошёл: {wh.get('description', 'Unknown error')}"
                )
            )
        else:
            info = wh['result']
            webhook_url = info.get('url', '')
            pending = info.get('pending_update_count', 0)
            last_error = info.get('last_error_message')

            if webhook_url:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Установлен webhook: {webhook_url}')
                )
                self.stdout.write(f'   Pending updates: {pending}')
                if last_error:
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ Последняя ошибка доставки webhook: {last_error}')
                    )
                    self.stdout.write(
                        '   Это значит Telegram НЕ может достучаться до сервера: '
                        'неверный URL, нет HTTPS/сертификата, или gunicorn не принимает '
                        'POST. Обновления (в т.ч. /start) не обрабатываются!'
                    )
                self.stdout.write(
                    self.style.WARNING(
                        '   ПОМНИТЕ: при установленном webhook polling (getUpdates) не работает '
                        '(409 Conflict). Используйте ТОЛЬКО один режим.'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('✅ Webhook не установлен — работаем через long polling.')
                )
                if pending:
                    self.stdout.write(
                        self.style.WARNING(f'   ⚠️ Но есть {pending} непрочитанных обновлений '
                                           '(это нормально для polling: они ждут getUpdates).')
                    )

        # 3. Статистика подписчиков в БД
        self.stdout.write(self.style.MIGRATE_HEADING('=== СТАТИСТИКА ПОДПИСЧИКОВ (БД) ==='))

        total_tg_users = TelegramUser.objects.count()
        linked_students = TelegramUser.objects.filter(
            student__isnull=False, is_parent=False
        ).count()
        linked_parents = TelegramUser.objects.filter(
            student__isnull=False, is_parent=True
        ).count()
        linked_teachers = TelegramUser.objects.filter(teacher__isnull=False).count()
        unlinked = TelegramUser.objects.filter(
            student__isnull=True, teacher__isnull=True
        ).count()

        self.stdout.write(f'Всего записей TelegramUser: {total_tg_users}')
        self.stdout.write(f'  - привязано учеников:      {linked_students}')
        self.stdout.write(f'  - привязано родителей:     {linked_parents}')
        self.stdout.write(f'  - привязано преподавателей: {linked_teachers}')
        if unlinked:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠️ без привязки к профилю: {unlinked} — эти пользователи нажимали '
                    '/start, но их @username не указан в профилях. Обработайте их командой:\n'
                    '    python manage.py sync_telegram_chat_ids'
                )
            )

        # chat_id у учеников
        students_total = Student.objects.count()
        students_with_chat = Student.objects.exclude(telegram_chat_id__isnull=True).count()
        students_with_parent_chat = Student.objects.exclude(
            parent_telegram_chat_id__isnull=True
        ).count()
        students_with_username = Student.objects.exclude(telegram_username='').count()
        students_with_parent_tg = Student.objects.exclude(parent_telegram='').count()

        self.stdout.write(f'Всего учеников: {students_total}')
        self.stdout.write(f'  - с chat_id ученика:   {students_with_chat}')
        self.stdout.write(f'  - с chat_id родителя:  {students_with_parent_chat}')
        self.stdout.write(f'  - с @username ученика: {students_with_username}')
        self.stdout.write(f'  - с @username родителя: {students_with_parent_tg}')

        without_any_chat = Student.objects.filter(
            telegram_chat_id__isnull=True,
            parent_telegram_chat_id__isnull=True,
        ).count()
        if without_any_chat:
            self.stdout.write(
                self.style.WARNING(
                    f'  ⚠️ {without_any_chat} учеников без chat_id (ни ученик, ни родитель '
                    'не нажимали /start у бота после привязки @username). '
                    'Уведомления им не доставятся, пока они не напишут боту /start. '
                    'Если @username указаны верно — привязку можно выполнить повторно:\n'
                    '    python manage.py sync_telegram_chat_ids'
                )
            )

        teacher_total = Teacher.objects.count()
        teacher_with_chat = Teacher.objects.exclude(telegram_chat_id__isnull=True).count()
        self.stdout.write(f'Всего преподавателей: {teacher_total} (с chat_id: {teacher_with_chat})')

        self.stdout.write(self.style.MIGRATE_HEADING('=== ИТОГ ==='))
        problems = []
        if not getattr(settings, 'TELEGRAM_BOT_ENABLED', False):
            problems.append('бот выключен: TELEGRAM_BOT_ENABLED=False')
        if wh.get('ok') and wh['result'].get('url') and wh['result'].get('last_error_message'):
            problems.append('webhook установлен, но Telegram не может доставить обновления')
        if unlinked:
            problems.append(f'{unlinked} записей TelegramUser без привязки к профилю')
        if without_any_chat:
            problems.append(
                f'{without_any_chat} учеников без chat_id (нужно нажать /start у бота)'
            )

        if problems:
            for p in problems:
                self.stdout.write(self.style.ERROR(f'⚠️ {p}'))
            self.stdout.write(
                self.style.WARNING(
                    'Порядок действий:\n'
                    '  1) python manage.py telegram_check (эта команда);\n'
                    '  2) python manage.py telegram_webhook --info — посмотреть webhook;\n'
                    '  3) выбрать ОДИН режим: polling (python manage.py telegram_webhook --unset, '
                    'затем запустить python manage.py telegram_polling)\n'
                    '     либо webhook (python manage.py telegram_webhook --set '
                    'https://mathphysedu.ru/students/telegram/webhook/);\n'
                    '  4) python manage.py sync_telegram_chat_ids — привязать /start к профилям;\n'
                    '  5) убедиться, что ученики/родители написали боту /start со своим @username.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Явных проблем не найдено.'))