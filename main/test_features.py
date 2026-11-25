from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (GuildEvent, EventRegistration, PartyListing, PartyResponse, Notification,
                     Person, Favorite, Category, Product, ProductVariant, MerchOrder, MerchOrderItem,
                     Poll, PollChoice, PollVote, Tournament, TournamentTeam, TournamentMatch, MatchReport, Publication)
from .services import change_order_status


class FeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('captain', 'captain@example.com', 'strong-test-pass-123')
        cls.player = get_user_model().objects.create_user('player', 'player@example.com', 'strong-test-pass-123')
        cls.event = GuildEvent.objects.create(title='Игра', description='Вечер', starts_at=timezone.now() + timedelta(days=1), capacity=1)
        cls.listing = PartyListing.objects.create(account=cls.owner, nickname='Капитан', schedule='вечером')

    def test_full_event_waitlist_promotes_first_player(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('event_register', args=[self.event.pk]), {'nickname': 'капитан', 'contact': '@captain'})
        self.client.force_login(self.player)
        self.client.post(reverse('event_register', args=[self.event.pk]), {'nickname': 'игрок', 'contact': '@player'})
        waiting = EventRegistration.objects.get(account=self.player)
        self.assertTrue(waiting.is_waiting)
        self.client.force_login(self.owner)
        self.client.post(reverse('event_cancel', args=[self.event.pk]))
        waiting.refresh_from_db()
        self.assertFalse(waiting.is_waiting)
        self.assertEqual(self.event.registered_count, 1)
        self.assertTrue(Notification.objects.filter(account=self.player).exists())

    def test_guest_cannot_cancel_account_registration(self):
        EventRegistration.objects.create(event=self.event, account=self.owner, nickname='капитан', visitor_key='same')
        session = self.client.session
        session['community_key'] = 'same'
        session.save()
        self.assertEqual(self.client.post(reverse('event_cancel', args=[self.event.pk])).status_code, 403)

    def test_party_acceptance_checks_roles_and_owner(self):
        response = PartyResponse.objects.create(listing=self.listing, account=self.player, nickname='игрок', contact='test', role='Мид / 2', visitor_key='one')
        url = reverse('party_accept', args=[self.listing.pk, response.pk])
        self.client.force_login(self.player)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.owner)
        self.client.post(url)
        response.refresh_from_db()
        self.assertTrue(response.is_accepted)
        duplicate = PartyResponse.objects.create(listing=self.listing, nickname='второй мидер', contact='test', role='Мид / 2', visitor_key='two')
        self.client.post(reverse('party_accept', args=[self.listing.pk, duplicate.pk]))
        duplicate.refresh_from_db()
        self.assertFalse(duplicate.is_accepted)
        self.client.post(url)
        response.refresh_from_db()
        self.assertFalse(response.is_accepted)

    def test_guest_response_is_not_duplicated_after_login(self):
        url = reverse('party_detail', args=[self.listing.pk])
        data = {'nickname': 'Игрок', 'contact': 'test', 'role': 'Мид / 2'}
        self.client.post(url, data)
        self.client.force_login(self.player)
        self.client.post(url, data)
        self.assertEqual(PartyResponse.objects.filter(listing=self.listing).count(), 1)

    def test_private_profile_is_hidden_everywhere(self):
        person = Person.objects.create(name='Скрытый', nickname='СекретныйНик', is_public=False)
        self.assertNotContains(self.client.get(reverse('people')), 'СекретныйНик')
        self.assertNotContains(self.client.get('/'), 'СекретныйНик')
        self.assertEqual(self.client.get(reverse('player_detail', args=[person.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('favorite_toggle', args=['person', person.pk])).status_code, 404)

    def test_favorites_and_notification_counts_are_private(self):
        person = Person.objects.create(name='Друг')
        self.client.force_login(self.owner)
        url = reverse('favorite_toggle', args=['person', person.pk])
        self.client.post(url)
        self.assertEqual(Favorite.objects.filter(account=self.owner).count(), 1)
        Notification.objects.create(account=self.owner, text='Твой отклик')
        self.assertEqual(self.client.get(reverse('notification_count')).json()['count'], 1)
        self.client.force_login(self.player)
        self.assertEqual(self.client.get(reverse('notification_count')).json()['count'], 0)
        self.assertNotContains(self.client.get(reverse('favorites')), 'Друг')

    def test_poll_one_vote_and_foreign_choice_rejected(self):
        poll = Poll.objects.create(title='Когда играем', closes_at=timezone.now() + timedelta(days=1))
        choice = PollChoice.objects.create(poll=poll, text='Сегодня')
        other_poll = Poll.objects.create(title='Что играем', closes_at=timezone.now() + timedelta(days=1))
        foreign = PollChoice.objects.create(poll=other_poll, text='Рейтинг')
        self.client.force_login(self.owner)
        url = reverse('poll_vote', args=[poll.pk])
        self.assertEqual(self.client.post(url, {'choice': foreign.pk}).status_code, 404)
        for _ in range(2):
            self.client.post(url, {'choice': choice.pk})
        self.assertEqual(PollVote.objects.count(), 1)

    def test_tournament_requires_five_players_and_one_team(self):
        tournament = Tournament.objects.create(title='Кубок', description='Игры', starts_at=timezone.now() + timedelta(days=3), registration_ends_at=timezone.now() + timedelta(days=2))
        url = reverse('tournament_detail', args=[tournament.pk])
        self.client.force_login(self.owner)
        self.client.post(url, {'name': 'Команда', 'roster': 'Один игрок'})
        self.assertEqual(TournamentTeam.objects.count(), 0)
        data = {'name': 'Команда', 'roster': 'Первый\nВторой\nТретий\nЧетвертый\nПятый'}
        self.client.post(url, data)
        self.client.post(url, data)
        self.assertEqual(TournamentTeam.objects.count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_token_link_without_exposing_account(self):
        response = self.client.post(reverse('password_reset'), {'email': self.owner.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/account/reset/', mail.outbox[0].body)
        response = self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    def test_rate_limit_applies_even_when_session_changes(self):
        for _ in range(10):
            self.client.post(reverse('signup'), {})
        self.client.cookies.clear()
        self.assertEqual(self.client.post(reverse('signup'), {}).status_code, 429)

    def test_search_does_not_expose_draft(self):
        Publication.objects.create(title='Публичный камбэк', body='Игра', is_published=True, kind='news')
        Publication.objects.create(title='Скрытый камбэк', body='Игра', kind='news')
        response = self.client.get(reverse('news'), {'q': 'камбэк'})
        self.assertContains(response, 'Публичный камбэк')
        self.assertNotContains(response, 'Скрытый камбэк')
        self.assertContains(self.client.get(reverse('news'), {'q': 'несуществующийтекст'}), 'Поиск публикаций')


class CancellationTests(TestCase):
    def test_admin_cancellation_uses_stock_service(self):
        admin = get_user_model().objects.create_superuser('stock-admin', 'admin@example.com', 'test-pass-123')
        category = Category.objects.create(name='Лето', category='Одежда')
        product = Product.objects.create(name='Худи', cat_id=category, sale=1000, material='Хлопок', data_prod=timezone.localdate(), counter=2)
        order = MerchOrder.objects.create(name='Игрок', contact='test', delivery='Город')
        MerchOrderItem.objects.create(order=order, product=product, name=product.name, quantity=1, price=1000)
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:main_merchorder_change', args=[order.pk]), {
            'name': order.name, 'contact': order.contact, 'delivery': order.delivery, 'status': 'cancelled',
            'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '1', 'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
            'items-0-id': str(order.items.get().pk), 'items-0-order': str(order.pk), '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(product.counter, 3)
        self.assertTrue(order.stock_returned)

    def test_repeated_checkout_does_not_reserve_twice(self):
        category = Category.objects.create(name='Лето', category='Одежда')
        product = Product.objects.create(name='Футболка', cat_id=category, sale=1000, material='Хлопок', data_prod=timezone.localdate(), counter=5)
        data = {'name': 'Игрок', 'contact': 'demo@example.com', 'delivery': 'Город', 'quantity': 1}
        for _ in range(2):
            self.client.post(reverse('merch_order', args=[product.pk]), data)
        self.assertEqual(MerchOrder.objects.count(), 1)
        product.refresh_from_db()
        self.assertEqual(product.counter, 4)

    def test_cancel_returns_stock_once_and_cannot_reopen(self):
        category = Category.objects.create(name='Мерч', category='Одежда')
        product = Product.objects.create(name='Худи', cat_id=category, sale=2500, material='Хлопок', data_prod=timezone.localdate(), counter=3)
        variant = ProductVariant.objects.create(product=product, size='M', stock=3)
        order = MerchOrder.objects.create(name='Игрок', contact='test', delivery='Город')
        MerchOrderItem.objects.create(order=order, product=product, name=product.name, size='M', quantity=2, price=2500)
        change_order_status(order.pk, 'cancelled')
        change_order_status(order.pk, 'cancelled')
        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(product.counter, 5)
        self.assertEqual(variant.stock, 5)
        with self.assertRaises(ValueError):
            change_order_status(order.pk, 'confirmed')


class DemoTests(TestCase):
    def test_refresh_removes_only_generated_merch_and_updates_existing_profiles(self):
        user = get_user_model().objects.create_user('demo_vetmo_1')
        person = Person.objects.create(account=user, name='Демо Кедр', nickname='[демо] Кедр')
        category = Category.objects.create(name='[демо] коллекция', category='Демонстрационный мерч')
        product = Product.objects.create(name='[демо] Футболка команды', cat_id=category, sale=1500, material='Хлопок', data_prod=timezone.localdate(), counter=17)
        real_category = Category.objects.create(name='лето', category='Одежда')
        existing = Product.objects.create(name='Футболка', cat_id=real_category, sale=2000, material='Хлопок', data_prod=timezone.localdate(), counter=10)
        with TemporaryDirectory() as directory, override_settings(DEBUG=True, BASE_DIR=Path(directory)):
            call_command('seed_demo', refresh=True, stdout=StringIO())
            person.refresh_from_db()
            self.assertEqual(person.nickname, 'sayro')
            self.assertFalse(Product.objects.filter(pk=product.pk).exists())
            self.assertTrue(Product.objects.filter(pk=existing.pk, counter=10).exists())
            counts = (Person.objects.count(), Publication.objects.count(), Poll.objects.count())
            call_command('seed_demo', refresh=True, stdout=StringIO())
            self.assertEqual(counts, (Person.objects.count(), Publication.objects.count(), Poll.objects.count()))
            for name in ('news', 'blog', 'events', 'party', 'matches', 'tournaments', 'polls'):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, '[демо]')
                self.assertNotContains(response, 'Вымышленный')

    def test_seed_is_repeatable_and_pages_render(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True, BASE_DIR=Path(directory)):
            call_command('seed_demo', stdout=StringIO())
            models = (Person, Product, GuildEvent, EventRegistration, PartyListing, PartyResponse, Tournament, TournamentTeam, PollVote, MerchOrder, MatchReport)
            counts = [model.objects.count() for model in models]
            call_command('seed_demo', stdout=StringIO())
            self.assertEqual(counts, [model.objects.count() for model in models])
            self.assertTrue((Path(directory) / '.local' / 'demo_accounts.json').exists())
            self.client.force_login(get_user_model().objects.get(username='demo_vetmo_1'))
            for name in ('account', 'events', 'matches', 'tournaments', 'polls', 'favorites', 'news', 'blog'):
                with self.subTest(name=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200)
            self.assertEqual(self.client.get(reverse('tournament_detail', args=[Tournament.objects.first().pk])).status_code, 200)

    def test_showcase_chronology_and_relationships(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True, BASE_DIR=Path(directory)):
            call_command('seed_demo', refresh=True, stdout=StringIO())
            now = timezone.now()
            completed = Tournament.objects.get(title='Осенний кап')
            self.assertEqual(completed.winner.name, 'late queue')
            self.assertLess(completed.registration_ends_at, completed.starts_at)
            self.assertFalse(completed.matches.filter(starts_at__gt=now).exists())
            upcoming = Tournament.objects.get(title='Вечерний кап')
            self.assertGreater(upcoming.registration_ends_at, now)
            self.assertFalse(upcoming.matches.exists())
            self.assertTrue(GuildEvent.objects.filter(starts_at__lt=now).exists())
            self.assertTrue(TournamentMatch.objects.filter(is_finished=False, starts_at__gt=now).exists())
            self.assertTrue(MatchReport.objects.filter(tournament_match__tournament=completed, players__nickname='sayro').exists())
            counts = (Tournament.objects.count(), TournamentMatch.objects.count(), MatchReport.objects.count())
            call_command('seed_demo', refresh=True, stdout=StringIO())
            self.assertEqual(counts, (Tournament.objects.count(), TournamentMatch.objects.count(), MatchReport.objects.count()))


class CommunityJourneyTests(TestCase):
    def test_email_error_preserves_address_without_changing_profile(self):
        user = get_user_model().objects.create_user('email-player', email='old@example.com', password='valid-pass')
        person = Person.objects.create(account=user, name='Игрок', nickname='original')
        self.client.force_login(user)
        response = self.client.post(reverse('account_email'), {'email': 'new@example.com', 'password': 'wrong'})
        self.assertContains(response, 'new@example.com')
        self.assertTrue(response.context['email_form'].errors)
        user.refresh_from_db()
        person.refresh_from_db()
        self.assertEqual(user.email, 'old@example.com')
        self.assertEqual(person.nickname, 'original')

    def test_event_validation_preserves_nickname_and_account_shows_waiting(self):
        event = GuildEvent.objects.create(title='Микс', starts_at=timezone.now() + timedelta(days=2), capacity=1)
        response = self.client.post(reverse('event_register', args=[event.pk]), {'nickname': 'мой ник', 'contact': ''})
        self.assertContains(response, 'мой ник')
        self.assertTrue(response.context['events'][0].registration_form.errors)
        self.assertFalse(event.registrations.exists())
        user = get_user_model().objects.create_user('new-player')
        self.client.force_login(user)
        EventRegistration.objects.create(event=event, nickname='капитан')
        self.client.post(reverse('event_register', args=[event.pk]), {'nickname': 'мой ник', 'contact': '@contact'})
        response = self.client.get(reverse('account'))
        self.assertContains(response, 'Ты в очереди')
        self.assertContains(response, reverse('events') + f'#event-{event.pk}')

    def test_player_filters_and_unknown_hero_fallback(self):
        Person.objects.create(name='Один', nickname='target', position='Мид / 2', mmr=4100,
                              goal='rating', play_schedule='будни 21:00', favorite_heroes='Puck, Неизвестный герой')
        Person.objects.create(name='Другой', nickname='other', mmr=2000, goal='fun')
        response = self.client.get(reverse('people'), {'goal': 'rating', 'mmr_min': 3500, 'schedule': '21:00'})
        self.assertContains(response, 'target')
        self.assertNotContains(response, '>other<')
        self.assertContains(response, '/heroes/puck.png')
        self.assertContains(response, 'Неизвестный герой')
        response = self.client.get(reverse('people'), {'mmr_min': 5000, 'mmr_max': 1000})
        self.assertTrue(response.context['filters'].errors)

    def test_report_links_respect_profile_visibility_and_tournament_publication(self):
        visible = Person.objects.create(name='Открытый', nickname='open-player')
        hidden = Person.objects.create(name='Скрытый', nickname='private-player', is_public=False)
        report = MatchReport.objects.create(title='Разбор', score='30:20', roster='Состав', analysis='Выводы')
        report.players.set([visible, hidden])
        response = self.client.get(reverse('matches'))
        self.assertContains(response, reverse('player_detail', args=[visible.pk]))
        self.assertNotContains(response, reverse('player_detail', args=[hidden.pk]))
        self.assertContains(self.client.get(reverse('player_detail', args=[visible.pk])), f'#match-{report.pk}')
        self.assertContains(self.client.get('/'), 'Разбор')
        report.played_at = timezone.now() + timedelta(days=1)
        report.save()
        self.assertNotContains(self.client.get('/'), f'#match-{report.pk}')
