import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from main.models import SupportBotState
from main.telegram_support import TelegramError, api, deliver_pending, receive_update


class Command(BaseCommand):
    help = 'Relay website support messages to Telegram and operator replies back to the website.'

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_SUPPORT_CHAT_ID:
            raise CommandError('Сначала выполните setup_support.')
        try:
            if api('getWebhookInfo').get('url'):
                raise CommandError('У бота установлен webhook. Используйте отдельного бота без webhook для поддержки.')
            self.stdout.write('Поддержка запущена. В Telegram используйте «Ответить» на сообщение посетителя. Ctrl+C — остановить.')
            state, _ = SupportBotState.objects.get_or_create(pk=1)
            while True:
                try:
                    close_old_connections()
                    deliver_pending()
                    updates = api('getUpdates', {'offset': state.offset, 'timeout': 3, 'allowed_updates': ['message']})
                    for update in updates:
                        receive_update(update)
                        state.offset = update['update_id'] + 1
                        state.save(update_fields=['offset'])
                except TelegramError as exc:
                    self.stderr.write(str(exc))
                    time.sleep(5)
        except TelegramError as exc:
            raise CommandError(str(exc)) from None
        except KeyboardInterrupt:
            self.stdout.write('Поддержка остановлена.')
