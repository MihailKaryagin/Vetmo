from datetime import datetime, timedelta, timezone as utc

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .community import CONFIRM_PREFIX, REMINDER_PREFIX, todays_series
from .models import GuildEvent, Notification, PartyListing, Person, Tournament, TournamentMatch


class EventJourneyTests(TestCase):
    def setUp(self):
        self.captain = get_user_model().objects.create_user('event-captain')
        self.member = get_user_model().objects.create_user('event-member')
        self.game = PartyListing.objects.create(account=self.captain, nickname='Saturday')
        for i, (role, _) in enumerate(PartyListing.ROLE_CHOICES[2:]):
            self.game.responses.create(account=self.member if i == 0 else None, role=role,
                                       is_accepted=True, visitor_key=str(i))
        self.at = timezone.now() + timedelta(minutes=45)

    def schedule(self, at):
        self.client.force_login(self.captain)
        self.client.post(reverse('party_start', args=[self.game.pk]), {'game_at': at.isoformat()})

    def test_move_and_return_to_original_time_reminds_once_again(self):
        Person.objects.create(account=self.member, name='M', remind_game=True)
        self.schedule(self.at)
        call_command('guild_tick')
        reminders = self.member.notifications.filter(text__startswith=REMINDER_PREFIX)
        self.assertEqual(reminders.count(), 1)
        self.schedule(self.at + timedelta(days=1))
        self.assertFalse(reminders.exists())
        self.schedule(self.at)
        call_command('guild_tick')
        call_command('guild_tick')
        self.assertEqual(reminders.count(), 1)
        self.assertEqual(self.member.notifications.filter(text__startswith=CONFIRM_PREFIX).count(), 1)
        Notification.objects.create(account=self.member, text='Новость')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('account')).context['notifications'][0].urgency, 2)
        self.client.post(reverse('party_confirm', args=[self.game.pk]))
        self.assertFalse(self.member.notifications.filter(text__startswith=CONFIRM_PREFIX).exists())

    def test_captain_calendar_and_conflict_before_registering(self):
        self.schedule(self.at)
        GuildEvent.objects.create(title='Other event', starts_at=self.at + timedelta(minutes=15))
        self.assertContains(self.client.get(reverse('account')), 'Ты капитан: Saturday')
        page = self.client.get(reverse('events'))
        self.assertContains(page, 'Возможное пересечение')
        self.assertContains(page, 'Записаться')

    def test_game_day_respects_local_midnight(self):
        now = datetime(2027, 1, 8, 20, 30, tzinfo=utc.utc)
        cup = Tournament.objects.create(title='Cup', starts_at=now, registration_ends_at=now)
        a = cup.teams.create(captain=self.captain, name='A')
        b = cup.teams.create(captain=self.member, name='B')
        for hours in (-2, 0, 23):
            TournamentMatch.objects.create(tournament=cup, team_a=a, team_b=b, starts_at=now+timedelta(hours=hours))
        with timezone.override('Asia/Yekaterinburg'):
            self.assertEqual(list(todays_series(now).values_list('starts_at', flat=True)), [now])

    def test_grouped_unread_count_tracks_pending_responses(self):
        game = PartyListing.objects.create(account=self.captain, nickname='New roster')
        role = PartyListing.ROLE_CHOICES[2][0]
        for name in ('One', 'Two'):
            Client().post(reverse('party_detail', args=[game.pk]), {'nickname': name, 'role': role, 'contact': '@friend', 'message': 'готов'})
        notices = self.captain.notifications.filter(url=reverse('party_detail', args=[game.pk]), is_read=False)
        self.assertIn('2 ждут ответа', notices.get().text)
        self.client.force_login(self.captain)
        self.client.post(reverse('party_accept', args=[game.pk, game.responses.first().pk]))
        self.assertIn('1 ждут ответа', notices.get().text)

    def test_move_notifies_registered_and_waiting_only_once(self):
        event = GuildEvent.objects.create(title='Reschedule', starts_at=self.at)
        for user, waiting in ((self.captain, False), (self.member, True)):
            event.registrations.create(account=user, nickname=user.username, visitor_key=user.username, is_waiting=waiting)
        event.starts_at += timedelta(days=1)
        for _ in range(2):
            admin.site._registry[GuildEvent].save_model(None, event, None, True)
        notices = Notification.objects.filter(url=reverse('events') + f'#event-{event.pk}')
        self.assertCountEqual(notices.values_list('account_id', flat=True), [self.member.pk, self.captain.pk])
        self.assertIn(timezone.localtime(self.at).strftime('%d.%m.%Y %H:%M'), notices.first().text)
        self.assertIn(timezone.localtime(event.starts_at).strftime('%d.%m.%Y %H:%M'), notices.first().text)
