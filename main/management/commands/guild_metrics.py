from datetime import timedelta
from django.db.models import Count, Q, Sum
from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import PartyListing, PartyResponse


class Command(BaseCommand):
    help = 'Сводка по объявлениям (просмотры страниц, не уникальные посетители)'

    def handle(self, **options):
        now = timezone.now()
        views = PartyListing.objects.aggregate(n=Sum('detail_views'))['n'] or 0
        counts = PartyResponse.objects.aggregate(
            total=Count('pk'),
            ever=Count('pk', filter=Q(is_accepted=True) | Q(accepted_at__isnull=False) | Q(removed_at__isnull=False)),
            accepted=Count('pk', filter=Q(is_accepted=True)),
            confirmed=Count('pk', filter=Q(is_accepted=True, confirmed_at__isnull=False, listing__game_at__isnull=False)),
            waiting=Count('pk', filter=Q(created_at__lt=now-timedelta(days=1), is_accepted=False,
                                         accepted_at=None, removed_at=None, listing__is_active=True,
                                         listing__expires_at__gt=now)),
        )
        self.stdout.write(f"Просмотры: {views}; отклики: {counts['total']}; принимались: {counts['ever']}; "
                          f"сейчас приняты: {counts['accepted']}; подтвердили текущее время: {counts['confirmed']}; "
                          f"ждут >24 ч: {counts['waiting']}")
