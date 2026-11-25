import gzip
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Проверить целостность копии без изменения базы данных'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, **options):
        path = Path(options['path'])
        try:
            checksum_path = path.with_name(path.name + '.sha256')
            if checksum_path.exists():
                expected = checksum_path.read_text(encoding='ascii').strip().split()[0]
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != expected:
                    raise ValueError('Контрольная сумма не совпадает')
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                rows = json.load(stream)
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('model'), str) or not isinstance(row.get('fields'), dict) for row in rows):
                raise ValueError('Неверный формат Django fixture')
        except (OSError, ValueError, EOFError, IndexError) as error:
            raise CommandError(f'Копия не прошла проверку: {error}') from error
        self.stdout.write(self.style.SUCCESS(f'Копия читается, записей: {len(rows)}. База данных не изменена. Для проверки восстановления загрузите её в отдельную базу.'))
