import json
import secrets
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from main.telegram_support import TelegramError, api


class Command(BaseCommand):
    help = 'Configure a bot token and bind its operator through a private Telegram /start link.'

    def handle(self, *args, **options):
        path = settings.BASE_DIR / '.local' / 'telegram.json'
        if path.exists():
            self.stdout.write('Настройки уже сохранены. Для повторной привязки удалите .local/telegram.json.')
            return
        token = input('Вставьте токен от @BotFather и нажмите Enter (ввод виден): ').strip()
        if not token:
            raise CommandError('Токен не введён.')
        try:
            bot = api('getMe', token=token)
            if api('getWebhookInfo', token=token).get('url'):
                raise CommandError('У этого бота есть webhook. Создайте отдельного бота для поддержки.')
            nonce = secrets.token_urlsafe(24)
            self.stdout.write(f'Откройте ссылку в своём Telegram и нажмите START:\nhttps://t.me/{bot["username"]}?start={nonce}\nОжидание привязки: 5 минут. Не передавайте эту ссылку другим.')
            deadline = time.monotonic() + 300
            offset = 0
            while time.monotonic() < deadline:
                for update in api('getUpdates', {'offset': offset, 'timeout': 20, 'allowed_updates': ['message']}, token=token):
                    offset = update['update_id'] + 1
                    message = update.get('message', {})
                    if message.get('chat', {}).get('type') != 'private' or message.get('text') != f'/start {nonce}':
                        continue
                    chat_id = message['chat']['id']
                    api('sendMessage', {'chat_id': chat_id, 'text': 'Поддержка подключена! Отвечайте на сообщения сайта через «Ответить». Текст ответа появится в чате посетителя.'}, token=token)
                    path.parent.mkdir(exist_ok=True)
                    path.write_text(json.dumps({'token': token, 'chat_id': chat_id}), encoding='utf-8')
                    self.stdout.write(self.style.SUCCESS('Токен и привязка сохранены в .local/telegram.json.'))
                    return
            raise CommandError('Время истекло. Запустите настройку ещё раз и нажмите START по новой ссылке.')
        except TelegramError as exc:
            raise CommandError(str(exc)) from None
