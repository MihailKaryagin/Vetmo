from datetime import time, timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ProfileForm
from .models import Person, PartyListing, PartyResponse, MatchReport, Notification, GuildEvent
from .opendota import update_match
from .scheduling import overlap_reason


class PlanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.captain = get_user_model().objects.create_user('planner')
        cls.member = get_user_model().objects.create_user('member')
        cls.listing = PartyListing.objects.create(account=cls.captain, nickname='captain', schedule='вечером')
        for i, role in enumerate(PartyListing.ROLE_CHOICES[2:]):
            PartyResponse.objects.create(listing=cls.listing, account=cls.member if i == 0 else None,
                nickname=f'player{i}', role=role[0], is_accepted=True, visitor_key=f'key-{i}', contact='discord')

    def test_schedule_confirm_and_roster_change_invalidate_time(self):
        url = reverse('party_start', args=[self.listing.pk])
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(url, {'game_at': (timezone.now() + timedelta(days=1)).isoformat()}).status_code, 403)
        self.client.force_login(self.captain)
        self.client.post(url, {'game_at': (timezone.now() + timedelta(days=1)).isoformat()})
        self.listing.refresh_from_db()
        self.assertIsNotNone(self.listing.game_at)
        self.assertEqual(Notification.objects.filter(account=self.member).count(), 1)
        self.client.force_login(self.member)
        self.client.post(reverse('party_confirm', args=[self.listing.pk]))
        member = self.listing.responses.get(account=self.member)
        member.refresh_from_db()
        self.assertIsNotNone(member.confirmed_at)
        response = self.client.get(reverse('party_calendar', args=[self.listing.pk]))
        self.assertContains(response, 'BEGIN:VCALENDAR')
        self.client.force_login(self.captain)
        self.client.post(reverse('party_accept', args=[self.listing.pk, member.pk]))
        self.listing.refresh_from_db()
        self.assertIsNone(self.listing.game_at)
        self.assertFalse(self.listing.responses.filter(confirmed_at__isnull=False).exists())

    def test_incomplete_roster_and_invalid_time_do_not_schedule(self):
        self.client.force_login(self.captain)
        url = reverse('party_start', args=[self.listing.pk])
        response = self.client.post(url, {'game_at': 'bad'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['start_form'].errors)
        self.listing.responses.first().delete()
        self.client.post(url, {'game_at': (timezone.now() + timedelta(days=1)).isoformat()})
        self.listing.refresh_from_db()
        self.assertIsNone(self.listing.game_at)

    def test_overlap_accounts_for_timezone_and_midnight(self):
        first = Person(name='A', timezone_name='Europe/Moscow', play_days=['0'], play_from=time(23), play_until=time(2))
        second = Person(name='B', timezone_name='Asia/Yekaterinburg', play_days=['1'], play_from=time(1), play_until=time(3))
        self.assertTrue(overlap_reason(first, second))
        second.play_days = ['3']
        self.assertEqual(overlap_reason(first, second), '')

    def test_profile_rejects_invalid_zone_and_incomplete_schedule(self):
        form = ProfileForm({'name': 'A', 'timezone_name': 'Wrong/Zone', 'play_days': ['0'], 'play_from': '20:00', 'status': 'looking', 'goal': 'team'})
        self.assertFalse(form.is_valid())
        self.assertIn('timezone_name', form.errors)

    def test_compatible_filter_excludes_nonoverlapping_players(self):
        Person.objects.create(account=self.captain, name='Капитан', timezone_name='Europe/Moscow',
            play_days=['0'], play_from=time(20), play_until=time(23))
        Person.objects.create(name='Подходит', nickname='overlap-player', timezone_name='Europe/Moscow',
            play_days=['0'], play_from=time(21), play_until=time(23))
        Person.objects.create(name='Не подходит', nickname='other-day-player', timezone_name='Europe/Moscow',
            play_days=['2'], play_from=time(21), play_until=time(23))
        self.client.force_login(self.captain)
        response = self.client.get(reverse('people'), {'compatible': 'on'})
        self.assertContains(response, 'overlap-player')
        self.assertNotContains(response, 'other-day-player')

    def test_calendar_escape_and_hidden_event(self):
        event = GuildEvent.objects.create(title='Игра, вечером\nещё строка', description='тест;описание', starts_at=timezone.now() + timedelta(days=1))
        response = self.client.get(reverse('event_calendar', args=[event.pk]))
        self.assertContains(response, r'Игра\, вечером\nещё строка')
        event.is_published = False
        event.save()
        self.assertEqual(self.client.get(reverse('event_calendar', args=[event.pk])).status_code, 404)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_error_pages_and_match_visibility(self):
        self.assertContains(self.client.get('/missing-page'), 'На этой линии никого', status_code=404)
        report = MatchReport.objects.create(title='Матч', score='1:0', roster='Игрок — Puck', analysis='Текст')
        self.assertContains(self.client.get(reverse('match_detail', args=[report.pk])), '/heroes/puck.png')
        report.is_published = False
        report.save()
        self.assertEqual(self.client.get(reverse('match_detail', args=[report.pk])).status_code, 404)

    def test_import_keeps_manual_content_and_handles_missing_data(self):
        report = MatchReport.objects.create(title='Матч', score='1:0', roster='Состав', analysis='Авторский текст')
        payload = {'match_id': 12345, 'duration': 2400, 'radiant_win': True, 'players': [{'hero_id': 13, 'kills': 10}]}
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with patch('main.opendota.urlopen', return_value=response):
            update_match(report, 12345)
        report.refresh_from_db()
        self.assertEqual(report.analysis, 'Авторский текст')
        self.assertEqual(report.duration, 2400)
        self.assertEqual(report.match_stats['players'][0]['hero_id'], 13)
        response.__enter__.return_value.read.return_value = b'{}'
        with patch('main.opendota.urlopen', return_value=response), self.assertRaises(ValueError):
            update_match(report, 999)
        report.refresh_from_db()
        self.assertEqual(report.match_id, 12345)

    def test_backup_checksum_detects_corruption(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.json.gz'
            call_command('backup_database', output=str(path), stdout=StringIO())
            call_command('verify_backup', str(path), stdout=StringIO())
            path.write_bytes(path.read_bytes() + b'corrupt')
            with self.assertRaises(CommandError):
                call_command('verify_backup', str(path), stdout=StringIO())
