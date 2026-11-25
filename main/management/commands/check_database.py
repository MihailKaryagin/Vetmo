from django.core.management.base import BaseCommand, CommandError
from django.db import connection, OperationalError


class Command(BaseCommand):
    help = 'Проверить подключение к базе перед запуском'
    requires_system_checks = []

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
        except OperationalError:
            raise CommandError(
                'База недоступна проверьте MYSQL параметры в .env '
                'и службу MySQL например Start-Service MYSQL84 в PowerShell администратора'
            ) from None
        self.stdout.write(self.style.SUCCESS('Подключение к базе работает'))
