from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone as utc
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Person, PartyListing, PartyResponse, Notification
from .scheduling import overlap_reason


class GuildTests(TestCase):
    def test_same_game_across_midnight(self):
        friday = datetime(2027, 1, 8, 20, 30, tzinfo=utc.utc)
        now = friday - timedelta(days=1)
        member = get_user_model().objects.create_user('timezone-member')
        profile = Person.objects.create(account=member, name='B', timezone_name='Asia/Yekaterinburg', play_days=['5'], play_from=time(1), play_until=time(3))
        captain = Person(name='A', timezone_name='Europe/Moscow', play_days=['4'], play_from=time(23), play_until=time(1))
        game = PartyListing.objects.create(nickname='Timezone', game_at=friday)
        game.responses.create(account=member, is_accepted=True, visitor_key='member')
        with patch('django.utils.timezone.now', return_value=now):
            self.client.force_login(member)
            self.assertIn('09.01 с 01:00', overlap_reason(profile, captain))
            self.assertContains(self.client.get(reverse('party_detail', args=[game.pk])), '09.01.2027 01:30')
            self.assertContains(self.client.get(reverse('party_calendar', args=[game.pk])), 'DTSTART:20270108T203000Z')

    def test_reminder_opt_in_repeat_and_reschedule(self):
        member = get_user_model().objects.create_user('reminder-member')
        Person.objects.create(account=member, name='B', remind_game=True)
        game = PartyListing.objects.create(nickname='G', game_at=timezone.now()+timedelta(minutes=35))
        game.responses.create(account=member, is_accepted=True, visitor_key='member')
        call_command('guild_tick'); call_command('guild_tick')
        self.assertEqual(Notification.objects.filter(account=member).count(), 1)
        game.game_at += timedelta(days=1); game.save()
        call_command('guild_tick')
        self.assertEqual(Notification.objects.filter(account=member).count(), 1)


@skipUnless(connection.vendor == 'mysql', 'Проверка блокировок InnoDB')
class ConcurrentCaptainTests(TransactionTestCase):
    def test_racing_accepts_for_one_slot(self):
        user = get_user_model().objects.create_user('captain')
        listing = PartyListing.objects.create(account=user, nickname='G')
        urls = [reverse('party_accept', args=[listing.pk, listing.responses.create(nickname=str(i), visitor_key=str(i), role='Мид / 2').pk]) for i in range(2)]
        barrier = Barrier(2)
        def accept(url):
            try:
                client = Client(); client.force_login(user); barrier.wait(timeout=15)
                return client.post(url).status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(accept, urls)), [302, 302])
        self.assertEqual(PartyResponse.objects.filter(listing=listing, is_accepted=True).count(), 1)
