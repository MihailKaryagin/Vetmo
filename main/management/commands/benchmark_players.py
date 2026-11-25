import hashlib
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from statistics import median
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main.models import PartyListing, Person


class Command(BaseCommand):
    help = 'Измерить HTTP-ответ списка игроков на выделенной MySQL-схеме guild_audit_*'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=0, metavar='N')
        parser.add_argument('--runs', type=int, default=30)
        parser.add_argument('--workers', type=int, default=1)

    def handle(self, seed, runs, workers, **options):
        name = os.environ.get('MYSQL_DATABASE', '')
        if (not name.startswith('guild_audit_') or connection.vendor != 'mysql'
                or connection.settings_dict['NAME'] != name):
            raise CommandError('Нужна отдельная MYSQL_DATABASE=guild_audit_*')
        if not 1 <= workers <= min(runs, 32) or seed < 0:
            raise CommandError('Неверный размер выборки')
        if ('main', '0019_guild_improvements') not in MigrationRecorder(connection).applied_migrations():
            raise CommandError('Для benchmark нужна схема с применённой миграцией main.0019')
        roles = [role for role, _ in PartyListing.ROLE_CHOICES[1:]]
        if seed:
            with transaction.atomic():
                if Person.objects.exists():
                    raise CommandError('--seed требует пустую таблицу игроков')
                for start in range(0, seed, 500):
                    Person.objects.bulk_create([
                        Person(name=f'Player{i}', nickname=f'Bench{i:06d}', position=roles[i % 5],
                               goal=('team', 'rating', 'fun')[i % 3], mmr=500 + (i * 137) % 8500,
                               is_public=i % 17 != 0, is_active=i % 19 != 0,
                               bio='Synthetic player. ' * 10, favorite_heroes='Axe, Lion')
                        for i in range(start, min(seed, start + 500))])
        params = dict(position=roles[1], goal='team', mmr_min=2500, sort='mmr', page=2)
        url = reverse('people')
        with override_settings(ALLOWED_HOSTS=['testserver']):
            def request(client):
                response = client.get(url, params)
                if response.status_code != 200 or response.content.count(b'class="feature-card person-card"') != 12:
                    raise CommandError('Ожидалась полная страница из 12 карточек')
                return response.content

            client = Client()
            body = request(client)  # warm templates and DB caches
            cards = re.findall(rb'<h2><a href="([^"]+)">', body)
            if len(cards) != 12:
                raise CommandError('Не удалось проверить идентичность карточек игроков')
            digest = hashlib.sha256(b'\n'.join(cards)).hexdigest()[:12]
            with CaptureQueriesContext(connection) as queries:
                request(client)

            def run_batch(n):
                local = Client()
                timings = []
                try:
                    for _ in range(n):
                        before = perf_counter()
                        request(local)
                        timings.append((perf_counter() - before) * 1000)
                finally:
                    connections.close_all()
                return timings

            with ThreadPoolExecutor(max_workers=workers) as pool:
                batches = pool.map(run_batch, [runs // workers + (i < runs % workers) for i in range(workers)])
                timings = [ms for batch in batches for ms in batch]
        self.stdout.write(f'players={Person.objects.count()} runs={runs} workers={workers} cards={digest} sql={len(queries)} '
                          f'p50_ms={median(timings):.2f} p95_ms={sorted(timings)[math.ceil(.95*runs)-1]:.2f}')
