"""Minimal Telegram Bot API client using the Python standard library."""
import json
import re
import ssl
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

from .models import SupportMessage


class TelegramError(Exception):
    pass


def api(method, payload=None, *, token=None):
    token = token if token is not None else settings.TELEGRAM_BOT_TOKEN
    if not isinstance(token, str) or not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise TelegramError('Некорректный формат токена. Скопируйте весь токен от @BotFather и вставьте правой кнопкой мыши или Shift+Insert, затем нажмите Enter.')
    request = Request(
        f'https://api.telegram.org/bot{token}/{method}',
        data=json.dumps(payload or {}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urlopen(request, timeout=40) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise TelegramError('Telegram отклонил запрос. Проверьте настройки бота.')
        return result['result']
    except HTTPError as exc:
        if exc.code in (401, 404):
            message = 'Telegram отклонил токен бота. Скопируйте актуальный токен целиком из @BotFather, без кавычек и пробелов.'
        elif exc.code == 409:
            message = 'Конфликт Telegram: остановите другие обработчики этого бота и проверьте, что у него нет webhook.'
        elif exc.code == 429:
            message = 'Telegram временно ограничил запросы. Подождите минуту и повторите запуск.'
        else:
            message = f'Telegram вернул HTTP {exc.code}. Повторите попытку позже.'
        raise TelegramError(message) from None
    except URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            message = 'Не удалось проверить HTTPS-сертификат Telegram. Проверьте дату и время Windows, сертификаты и HTTPS-фильтрацию антивируса или прокси.'
        elif isinstance(exc.reason, (TimeoutError, OSError)) and getattr(exc.reason, 'winerror', None) in (10060, 10061, 10065):
            message = 'Соединение с api.telegram.org заблокировано или недоступно. Проверьте интернет, VPN, прокси и брандмауэр.'
        else:
            message = 'Не удалось подключиться к api.telegram.org. Проверьте интернет, DNS, VPN и настройки прокси Windows.'
        raise TelegramError(message) from None
    except (TimeoutError, OSError, ValueError, HTTPException):
        # Never include request URLs: they contain the secret token.
        raise TelegramError('Соединение с Telegram прервалось или ответ не получен. Проверьте интернет и повторите попытку.') from None


def deliver_pending():
    for message in SupportMessage.objects.filter(from_operator=False, telegram_message_id__isnull=True)[:20]:
        sent = api('sendMessage', {
            'chat_id': settings.TELEGRAM_SUPPORT_CHAT_ID,
            'text': f'💬 Чат сайта · {str(message.conversation_id)[:8]}\n\n{message.text}\n\nОтветьте на это сообщение через «Ответить».',
        })
        message.telegram_message_id = sent['message_id']
        message.save(update_fields=['telegram_message_id'])


def receive_update(update):
    message = update.get('message', {})
    if str(message.get('chat', {}).get('id')) != str(settings.TELEGRAM_SUPPORT_CHAT_ID):
        return
    reply_id = message.get('reply_to_message', {}).get('message_id')
    text = message.get('text', '').strip()
    if not text or not reply_id:
        return
    original = SupportMessage.objects.filter(telegram_message_id=reply_id, from_operator=False).first()
    if original:
        with transaction.atomic():
            SupportMessage.objects.get_or_create(
                telegram_update_id=update['update_id'],
                defaults={'conversation': original.conversation, 'text': text, 'from_operator': True},
            )
