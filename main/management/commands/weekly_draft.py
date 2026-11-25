from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import Publication, MatchReport, TournamentMatch, GuildEvent


class Command(BaseCommand):
    help = 'Создать неопубликованный черновик итогов недели для редактора'

    def handle(self, **options):
        now = timezone.now()
        recent = (now - timedelta(days=7), now)
        body = ['Завершённые серии']
        for m in TournamentMatch.objects.filter(tournament__is_published=True, is_finished=True, starts_at__range=recent).select_related('team_a', 'team_b'):
            body.append(f'{m.team_a} — {m.team_b}: {m.score_a}:{m.score_b}')
        body += ['Разборы', *MatchReport.objects.filter(is_published=True, played_at__range=recent).values_list('title', flat=True), 'В планах']
        body += [f'{timezone.localtime(e.starts_at):%d.%m %H:%M} — {e.title}' for e in GuildEvent.objects.filter(is_published=True, is_cancelled=False, starts_at__range=(now, now+timedelta(days=7)))]
        obj, created = Publication.objects.get_or_create(title=f'Итоги недели · {timezone.localdate():%G-W%V}', kind='news', defaults={'body':'\n\n'.join(body), 'is_published':False})
        self.stdout.write(f'Публикация #{obj.pk}: ' + ('черновик создан' if created else 'уже существует'))
