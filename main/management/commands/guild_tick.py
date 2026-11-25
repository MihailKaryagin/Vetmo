from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from main.models import Notification, PartyListing, PartyResponse, Person
from main.community import REMINDER_PREFIX
from main.scheduling import player_zone


class Command(BaseCommand):
    help = 'Обновить временные статусы и отправить наступившие напоминания'

    def handle(self, **options):
        now = timezone.now()
        for p in Person.objects.filter(status='looking', looking_until__lte=now.date() + timedelta(days=1)):
            if p.looking_until < now.astimezone(player_zone(p)).date():
                Person.objects.filter(pk=p.pk, status='looking', looking_until=p.looking_until).update(status='busy', looking_until=None)
        games = PartyListing.objects.filter(is_active=True, game_at__gt=now, game_at__lte=now + timedelta(hours=1))
        for pk in games.values_list('pk', flat=True):
            with transaction.atomic():
                game = games.select_for_update().filter(pk=pk).first()
                if not game:
                    continue
                url = reverse('party_detail', args=[pk])
                text = f'{REMINDER_PREFIX} {game.nickname}. Проверь время старта.'
                if game.account_id and Person.objects.filter(account_id=game.account_id, remind_game=True).exists():
                    Notification.objects.get_or_create(account_id=game.account_id, url=url, text=text)
                for member in PartyResponse.objects.filter(listing=game, is_accepted=True, account__player_profile__remind_game=True):
                    if member.reminded_for != game.game_at:
                        Notification.objects.create(account_id=member.account_id, text=text, url=url)
                        member.reminded_for = game.game_at
                        member.save(update_fields=['reminded_for'])
