import gzip
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


class Command(BaseCommand):
    help = 'Сохранить переносимую копию данных в сжатом формате'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Путь к новому файлу json.gz')

    def handle(self, *args, **options):
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError('Сначала примените миграции командой manage.py migrate')
        target = Path(options['output']) if options['output'] else settings.BASE_DIR / 'backups' / timezone.now().strftime('vetmo-%Y%m%d-%H%M%S.json.gz')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            # перед копированием останавливаем запись на сайт
            with transaction.atomic():
                with gzip.open(target, 'xt', encoding='utf-8') as stream:
                    call_command('dumpdata', natural_foreign=True, natural_primary=True,
                                 exclude=['contenttypes', 'auth.permission', 'sessions'], stdout=stream)
        except FileExistsError:
            raise CommandError('Файл уже существует выберите новое имя') from None
        except Exception:
            if target.exists():
                target.unlink()
            raise
        with target.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        target.with_name(target.name + '.sha256').write_text(digest + '\n', encoding='ascii')
        self.stdout.write(self.style.SUCCESS(f'Копия сохранена {target}'))
