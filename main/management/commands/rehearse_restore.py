import gzip
import json
import os
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection


CHECKED = ('main.partylisting', 'main.partyresponse', 'main.eventregistration', 'main.tournamentteam')


def snapshot(rows):
    result = {}
    for row in rows:
        if row['model'] not in CHECKED:
            continue
        fields = dict(row['fields'])
        if row['model'] == 'main.tournamentteam':
            fields['players'] = sorted(fields.get('players', []))
        key = (row['model'], row['pk'])
        if key in result:
            raise CommandError(f'Повторный ключ в копии: {key}')
        result[key] = fields
    return result


class Command(BaseCommand):
    help = 'Проверить восстановление в одноразовой локальной SQLite базе'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, path, **options):
        source = Path(path).resolve()
        if not source.is_file():
            raise CommandError('Файл копии не найден')
        if not source.with_name(source.name + '.sha256').is_file():
            raise CommandError('Для репетиции нужен файл .sha256 рядом с копией')
        with TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'backup.json.gz'
            shutil.copyfile(source, fixture)
            shutil.copyfile(str(source) + '.sha256', str(fixture) + '.sha256')
            call_command('verify_backup', str(fixture), stdout=self.stdout)
            result = subprocess.run([sys.executable, '-m', __package__ + '.rehearse_restore', str(fixture)],
                                    cwd=settings.BASE_DIR, env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
                                                               'DJANGO_SETTINGS_MODULE': 'config.settings'},
                                    capture_output=True, text=True, encoding='utf-8')
            if result.returncode:
                raise CommandError(f'Ошибка репетиции: {result.stderr.strip()}')
            self.stdout.write(result.stdout.strip())


if __name__ == '__main__':
    import django

    # Even unqualified ORM calls in migrations and signal handlers use only SQLite.
    source, = sys.argv[1:]
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                                      'NAME': str(Path(source).with_name('restore.sqlite3'))}}
    django.setup()
    call_command('migrate', interactive=False, verbosity=0)
    call_command('loaddata', source, verbosity=0)
    with gzip.open(source, 'rt', encoding='utf-8') as f:
        expected = snapshot(json.load(f))
    stream = StringIO()
    call_command('dumpdata', *CHECKED, stdout=stream, natural_foreign=True, natural_primary=True)
    if snapshot(json.loads(stream.getvalue())) != expected:
        raise CommandError('После восстановления составы или регистрации отличаются от копии')
    connection.check_constraints()
    print(f'SQLite: проверены строки составов и регистраций ({len(expected)}), M2M и внешние ключи.')
