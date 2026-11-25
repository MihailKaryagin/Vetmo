from datetime import datetime, time, timedelta, timezone as utc
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PartyListing, Person


class PartyMatchingTests(TestCase):
    def setUp(self):
        self.player = get_user_model().objects.create_user('player')
        self.profile = Person.objects.create(account=self.player, name='P', position='Мид / 2', backup_position='Поддержка / 4')
        self.client.force_login(self.player)

    def test_primary_role_beyond_first_page_beats_recent_backups(self):
        first = PartyListing.objects.create(nickname='primary', role=self.profile.position)
        PartyListing.objects.bulk_create([PartyListing(nickname=str(i), role=self.profile.backup_position) for i in range(55)])
        self.assertEqual(self.client.get('/').context['recommended'], first)
        self.assertEqual(self.client.get(reverse('party')).context['listings'][0], first)

    def test_empty_search_relaxes_one_condition_and_counts_matches(self):
        for mic in [True, True, False]:
            PartyListing.objects.create(nickname='candidate', mmr_min=3000, microphone=mic)
        response = self.client.get(reverse('party'), {'mmr': 100, 'microphone': 'on'})
        suggestion = response.context['suggestion']
        self.assertEqual(suggestion['count'], 2)
        self.assertEqual(len(self.client.get(reverse('party') + '?' + suggestion['query']).context['listings']), 2)

    def test_evening_and_compatible_must_match_same_window(self):
        now = datetime(2027, 1, 8, 12, tzinfo=utc.utc)  # Friday
        captain = get_user_model().objects.create_user('captain')
        Person.objects.create(account=captain, name='C', play_days=['4', '5'], play_from=time(18), play_until=time(22))
        self.profile.play_days, self.profile.play_from, self.profile.play_until = ['5'], time(18), time(22)
        self.profile.save()
        PartyListing.objects.create(account=captain, expires_at=now+timedelta(days=3))
        with patch('django.utils.timezone.now', return_value=now):
            self.client.force_login(self.player)
            url = reverse('party')
            self.assertEqual(len(self.client.get(url, {'evening': 'on'}).context['listings']), 1)
            self.assertEqual(len(self.client.get(url, {'compatible': 'on'}).context['listings']), 1)
            self.assertEqual(len(self.client.get(url, {'evening': 'on', 'compatible': 'on'}).context['listings']), 0)

    def test_expired_history_and_renewal_belong_to_correct_accounts(self):
        owner = get_user_model().objects.create_user('owner')
        listing = PartyListing.objects.create(account=owner, expires_at=timezone.now()-timedelta(days=1))
        member = listing.responses.create(account=self.player, visitor_key='key')
        action = reverse('roster_action', args=[listing.pk, 'renew'])
        self.assertEqual(self.client.post(action).status_code, 403)
        detail = reverse('party_detail', args=[listing.pk])
        self.assertContains(self.client.get(detail), 'Срок набора истёк')
        self.client.logout()
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(owner)
        now = timezone.now()
        with patch('django.utils.timezone.now', return_value=now):
            self.client.post(action)
        listing.refresh_from_db()
        self.assertEqual(listing.expires_at, now+timedelta(days=7))
        self.client.post(reverse('roster_action', args=[listing.pk, 'decline']), {'response': member.pk})
        self.client.force_login(self.player)
        self.assertContains(self.client.get(reverse('account')), 'Отклик отклонён')
