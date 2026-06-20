from django.core.management.base import BaseCommand
from students.telegram_bot import sync_telegram_chat_ids


class Command(BaseCommand):
    help = 'Синхронизирует Telegram chat_id из getUpdates с моделями Student и Teacher'

    def handle(self, *args, **options):
        self.stdout.write('Syncing Telegram chat IDs...')
        count = sync_telegram_chat_ids()
        if count is not None:
            self.stdout.write(self.style.SUCCESS(f'Sync complete. Updated {count} records.'))
        else:
            self.stdout.write(self.style.ERROR('Sync failed. Check logs for details.'))