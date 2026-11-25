from django.core.management.base import BaseCommand, CommandError
from main.models import MatchReport
from main.opendota import update_match


class Command(BaseCommand):
    help = 'Загрузить статистику OpenDota для существующего разбора по его ID'

    def add_arguments(self, parser):
        parser.add_argument('report', type=int)
        parser.add_argument('match_id', type=int)

    def handle(self, *args, **options):
        try:
            report = MatchReport.objects.get(pk=options['report'])
            update_match(report, options['match_id'])
        except (MatchReport.DoesNotExist, ValueError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS('Статистика загружена. Авторский разбор и состав сохранены.'))
