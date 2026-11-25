import json
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from .models import SupportMessage
from .telegram_support import TelegramError, api, deliver_pending, receive_update


class TelegramTokenTests(SimpleTestCase):
    @patch('main.telegram_support.urlopen')
    def test_token_rejection_is_distinct_from_network_failure(self, urlopen):
        urlopen.side_effect = HTTPError('https://example.invalid', 401, 'Unauthorized', {}, None)
        with self.assertRaisesMessage(TelegramError, 'отклонил токен'):
            api('getMe', token='123:example')
        urlopen.side_effect = URLError('DNS unavailable')
        with self.assertRaisesMessage(TelegramError, 'Не удалось подключиться'):
            api('getMe', token='123:example')

    @patch('main.telegram_support.urlopen')
    def test_invalid_token_is_rejected_before_network_request(self, urlopen):
        for token in ('\x16', '123:secret\x16', 'not-a-token', ''):
            with self.subTest(token=repr(token)):
                with self.assertRaises(TelegramError) as error:
                    api('getMe', token=token)
                self.assertIn('формат токена', str(error.exception))
        urlopen.assert_not_called()


@override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_SUPPORT_CHAT_ID=123)
class SupportTests(TestCase):
    def setUp(self):
        self.url = reverse('support_messages')

    def send(self, client, text='Нужна помощь'):
        return client.post(self.url, json.dumps({'text': text}), content_type='application/json')

    def test_sessions_are_isolated_and_cannot_select_another_conversation(self):
        first, second = Client(), Client()
        self.assertEqual(self.send(first).status_code, 201)
        original = SupportMessage.objects.get()
        self.assertEqual(second.get(self.url, {'conversation': str(original.conversation_id)}).json()['messages'], [])
        self.assertEqual(self.send(second, 'Другой посетитель').status_code, 201)
        self.assertEqual([m['text'] for m in first.get(self.url).json()['messages']], ['Нужна помощь'])

    @patch('main.telegram_support.api')
    def test_delivery_and_authorized_reply_are_routed_and_deduplicated(self, api):
        self.send(self.client)
        api.return_value = {'message_id': 42}
        deliver_pending()
        deliver_pending()
        self.assertEqual(api.call_count, 1)
        update = {'update_id': 100, 'message': {
            'chat': {'id': 999}, 'text': '<script>Ответ</script>',
            'reply_to_message': {'message_id': 42},
        }}
        receive_update(update)
        self.assertFalse(SupportMessage.objects.filter(from_operator=True).exists())
        update['message']['chat']['id'] = 123
        receive_update(update)
        receive_update(update)
        self.assertEqual(SupportMessage.objects.filter(from_operator=True).count(), 1)
        messages = self.client.get(self.url, {'after': SupportMessage.objects.first().pk}).json()['messages']
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['text'], '<script>Ответ</script>')
        self.assertTrue(messages[0]['from_operator'])

    def test_limits_and_bad_payloads(self):
        self.assertEqual(self.send(self.client, ' ').status_code, 400)
        self.assertEqual(self.send(self.client, 'x' * 2001).status_code, 400)
        self.assertEqual(self.client.post(self.url, '[]', content_type='application/json').status_code, 400)
        for _ in range(10):
            self.assertEqual(self.send(self.client).status_code, 201)
        self.assertEqual(self.send(self.client).status_code, 429)
        self.assertEqual(self.client.get(self.url, {'after': 'bad'}).status_code, 400)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.send(client).status_code, 403)
        client.get(self.url)
        response = client.post(self.url, json.dumps({'text': 'Помогите'}), content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201)

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_support_works_without_telegram(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.send(self.client).status_code, 201)


class SupportAdminTests(TestCase):
    def test_close_reopen_clear_and_colored_reply(self):
        self.grant('change_supportconversation')
        self.client.post(self.chat_url, {'text': 'Цветной ответ', 'color': '#e4b1ff'})
        reply = SupportMessage.objects.filter(from_operator=True).get()
        self.assertEqual(reply.color, '#e4b1ff')
        feed = self.visitor.get(reverse('support_messages')).json()
        self.assertEqual(feed['messages'][-1]['color'], '#e4b1ff')
        self.client.post(self.chat_url, {'text': 'Недопустимый цвет', 'color': 'red;display:none'})
        self.assertEqual(SupportMessage.objects.filter(from_operator=True).count(), 1)
        self.client.post(self.chat_url, {'action': 'close'})
        self.assertTrue(self.visitor.get(reverse('support_messages')).json()['is_closed'])
        self.assertEqual(self.visitor.post(reverse('support_messages'), json.dumps({'text': 'Ещё вопрос'}), content_type='application/json').status_code, 409)
        self.client.post(self.chat_url, {'text': 'Нельзя отправить'})
        self.assertEqual(SupportMessage.objects.filter(from_operator=True).count(), 1)
        self.client.post(self.chat_url, {'action': 'reopen'})
        self.assertFalse(self.visitor.get(reverse('support_messages')).json()['is_closed'])
        self.client.post(self.chat_url, {'action': 'clear'})
        feed = self.visitor.get(reverse('support_messages'), {'after': reply.pk, 'revision': 0}).json()
        self.assertEqual(feed['messages'], [])
        self.assertEqual(feed['revision'], 1)
        self.assertEqual(self.client.get(self.feed_url).json()['revision'], 1)
        self.client.post(self.chat_url, {'text': 'После очистки'})
        feed = self.visitor.get(reverse('support_messages'), {'after': reply.pk, 'revision': 0}).json()
        self.assertEqual([row['text'] for row in feed['messages']], ['После очистки'])

    def setUp(self):
        self.visitor = Client()
        self.visitor.post(reverse('support_messages'), json.dumps({'text': 'Помогите <script>test</script>'}), content_type='application/json')
        self.message = SupportMessage.objects.get()
        self.conversation = self.message.conversation
        self.chat_url = reverse('admin:main_supportconversation_change', args=[self.conversation.pk])
        self.feed_url = reverse('admin:main_supportconversation_messages', args=[self.conversation.pk])
        self.inbox_url = reverse('admin:main_supportconversation_changelist')
        self.operator = get_user_model().objects.create_user(username='operator', is_staff=True)

    def grant(self, codename):
        self.operator.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label='main'))
        self.client.force_login(self.operator)

    def test_operator_reply_reaches_only_original_visitor(self):
        self.grant('change_supportconversation')
        self.assertContains(self.client.get(self.inbox_url), 'Ждёт ответа')
        self.assertContains(self.client.get(self.chat_url), 'Отправить ответ')
        self.assertEqual(self.client.get(self.feed_url).json()['messages'][0]['text'], self.message.text)
        response = self.client.post(self.chat_url, {'text': 'Ответ поддержки'})
        self.assertRedirects(response, self.chat_url)
        messages = self.visitor.get(reverse('support_messages'), {'after': self.message.pk}).json()['messages']
        self.assertEqual([m['text'] for m in messages], ['Ответ поддержки'])
        self.assertTrue(messages[0]['from_operator'])
        self.assertEqual(Client().get(reverse('support_messages')).json()['messages'], [])
        self.assertContains(self.client.get(self.inbox_url), 'Ответ отправлен')

    def test_permissions_cover_page_feed_and_reply(self):
        self.assertEqual(self.client.get(self.feed_url).status_code, 302)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.chat_url).status_code, 403)
        self.assertEqual(self.client.get(self.feed_url).status_code, 403)
        self.assertEqual(self.client.post(self.chat_url, {'text': 'Недопустимо'}).status_code, 403)
        for action in ('close', 'clear', 'reopen'):
            self.assertEqual(self.client.post(self.chat_url, {'action': action}).status_code, 403)
        self.grant('view_supportconversation')
        self.assertEqual(self.client.get(self.chat_url).status_code, 200)
        self.assertEqual(self.client.get(self.feed_url).status_code, 200)
        self.assertEqual(self.client.post(self.chat_url, {'text': 'Недопустимо'}).status_code, 403)
        self.assertFalse(SupportMessage.objects.filter(from_operator=True).exists())

    def test_reply_validation_and_csrf(self):
        self.grant('change_supportconversation')
        self.assertContains(self.client.post(self.chat_url, {'text': ' '}), 'Обязательное поле')
        self.assertEqual(self.client.post(self.chat_url, {'text': 'x' * 2001}).status_code, 200)
        self.assertFalse(SupportMessage.objects.filter(from_operator=True).exists())
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.operator)
        self.assertEqual(protected.post(self.chat_url, {'text': 'Ответ'}).status_code, 403)
        protected.get(self.chat_url)
        self.assertEqual(protected.post(self.chat_url, {'text': 'Ответ'}, HTTP_X_CSRFTOKEN=protected.cookies['csrftoken'].value).status_code, 302)
