from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TransactionTestCase
from django.utils import timezone

from main.models import (EventRegistration, GuildEvent, PartyListing, PartyResponse,
                         Person, Tournament, TournamentTeam)


class AuditCommandsTests(TransactionTestCase):
    def test_restore_and_metrics(self):
        now = timezone.now()
        user = get_user_model().objects.create(username='synthetic-captain')
        tournament = Tournament.objects.create(title='Cup', starts_at=now, registration_ends_at=now)
        team = TournamentTeam.objects.create(tournament=tournament, captain=user, name='Team', roster='One, Two')
        team.players.add(Person.objects.create(name='One'), Person.objects.create(name='Two'))
        event = GuildEvent.objects.create(title='Game', starts_at=now)
        EventRegistration.objects.create(event=event, nickname='One', account=user)
        EventRegistration.objects.create(event=event, nickname='Two', is_waiting=True)
        listing = PartyListing.objects.create(nickname='Captain', account=user, detail_views=9, game_at=now)
        expired = PartyListing.objects.create(nickname='Expired', expires_at=now)
        for index, (parent, state) in enumerate([
            (listing, {'is_accepted': True, 'accepted_at': now, 'confirmed_at': now}),
            (listing, {'accepted_at': now, 'removed_at': now}), (listing, {}), (expired, {})
        ]):
            PartyResponse.objects.create(listing=parent, nickname=f'Guest{index}', visitor_key=str(index), **state)
        PartyResponse.objects.update(created_at=now - timedelta(hours=25))
        stream = StringIO()
        call_command('guild_metrics', stdout=stream)
        self.assertIn('Просмотры: 9; отклики: 4; принимались: 2; сейчас приняты: 1; '
                      'подтвердили текущее время: 1; ждут >24 ч: 1', stream.getvalue())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.json.gz'
            call_command('backup_database', output=str(path), stdout=stream)
            call_command('rehearse_restore', str(path), stdout=stream)
            self.assertIn('регистраций (9)', stream.getvalue())
            path.with_name(path.name + '.sha256').write_text('0' * 64, encoding='ascii')
            with self.assertRaises(CommandError):
                call_command('rehearse_restore', str(path), stdout=stream)
