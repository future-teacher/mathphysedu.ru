from django.core.management.base import BaseCommand
from students.telegram_bot import process_updates


class Command(BaseCommand):
    help = 'Обрабатывает входящие сообщения Telegram бота (отвечает на /start)'

    def handle(self, *args, **options):
        self.stdout.write('Processing Telegram updates...')
        count = process_updates()
        if count is not None:
            self.stdout.write(self.style.SUCCESS(f'Processed {count} updates.'))
        else:
            self.stdout.write(self.style.ERROR('Failed to process updates. Check logs.'))