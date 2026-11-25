from datetime import timedelta, time
import json
import secrets
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from main.models import (Person, Publication, Category, Product, GuildEvent, EventRegistration,
                         PartyListing, PartyResponse, Notification, Favorite, Achievement,
                         PlayerAchievement, MatchReport, Tournament, TournamentTeam,
                         TournamentMatch, Poll, PollChoice, PollVote, MerchOrder, MerchOrderItem, FormResult)


PLAYERS = (
    ('Данил', 'sayro', 3420, 'Керри / 1', 'будни 20:00–23:30', 'Juggernaut, Luna, Lifestealer', 'Керри, который приходит к назначенному времени и иногда даже к драке. На Luna играю от стака и первого BKB, на Lifestealer могу раньше подключиться к тройке. Ищу постоянную пятёрку на две-три карты после работы.'),
    ('Артём', 'kiyo', 4180, 'Мид / 2', 'вт чт сб после 21:00', 'Puck, Ember Spirit, Storm Spirit', 'Люблю мобильных мидеров и игры, где шестую руну не приходится оспаривать в одиночку. Перед выходом называю цель и прошу один TP за спину. После игры могу посмотреть линию в реплее — свою тоже.'),
    ('Никита', 'сын катапульты', 2870, 'Оффлейн / 3', 'выходные 16:00–22:00', 'Mars, Underlord, Centaur Warrunner', 'На тройке играю от линии: вынести блинк, занять чужой лес, дать керри спокойно добрать слот. Предпочитаю четвёрку с голосом и планом на первые уровни. Арену ставлю уверенно; кто в ней окажется — уже детали.'),
    ('Илья', 'sae', 3760, 'Поддержка / 4', 'почти каждый день после 19:30', 'Rubick, Tusk, Hoodwink', 'Четвёрка с привычкой смотреть на часы: лотос, руна, стаки. На Rubick сначала ищу позицию, потом красивый спелл. Хочу сыграться с одной тройкой, чтобы каждую карту не знакомиться заново на первом пулле.'),
    ('Максим', 'диспетчер', 3210, 'Полная поддержка / 5', 'пн ср пт 20:00–23:00', 'Oracle, Jakiro, Disruptor', 'Пятёрка. Помогаю пережить линию, собираю сейв по игре, перед Рошаном обновляю вижен. На Oracle лучше заранее сказать, что собираешься прыгать: по интонации «ой» не всегда успеваю.'),
    ('Андрей', 'греча', 4650, 'Керри / 1', 'после 22:00 по Москве', 'Morphling, Terrorblade, Sven', 'Поздний рейтинг, обычно до трёх карт. На Morphling много играю соло, в стаке хочу лучше отработать тайминги вокруг второго Рошана. Могу сам вести по карте, но во время драки оставляю эфир тому, кто видит больше.'),
    ('Саша', 'на две', 2540, 'Поддержка / 4', 'сб вс с 18:00', 'Dark Willow, Lion, Mirana', 'По выходным играю обычки и пробую героев вне привычного пула. На Mirana предпочитаю стрелу под стан, хотя иногда хочется поверить в себя. Рейтинг тоже можно, если заранее договоримся о ролях.'),
    ('Кирилл', 'velto', 3890, 'Мид / 2', 'будни 19:00–22:00', 'Queen of Pain, Leshrac, Void Spirit', 'Вернулся после перерыва, сейчас возвращаю чувство линии на QoP и Leshrac. Не обещаю выиграть каждый мид, зато скажу о пропаже сразу, а не после двойного убийства внизу. Ищу стак для регулярных игр и коротких разборов.'),
)


class Command(BaseCommand):
    help = 'Добавить данные для локального показа сайта'

    def add_arguments(self, parser):
        parser.add_argument('--refresh', action='store_true', help='Обновить тексты ранее созданных примеров')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Примеры доступны только в режиме разработки')
        now = timezone.now()
        folder = settings.BASE_DIR / '.local'
        folder.mkdir(exist_ok=True)
        path = folder / 'showcase_records.json'
        registry = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

        def record(key, model, lookup, values, legacy=None):
            # сохраняем привязки отдельно чтобы не ставить метки на сайте
            obj = model.objects.filter(pk=registry.get(key)).first() if key in registry else None
            if obj is None and legacy:
                obj = model.objects.filter(**legacy).first()
            if obj is None:
                obj, created = model.objects.get_or_create(**lookup, defaults=values)
            if options['refresh']:
                for field, value in values.items():
                    setattr(obj, field, value)
                obj.save()
            registry[key] = str(obj.pk) if isinstance(obj.pk, uuid.UUID) else obj.pk
            return obj

        users = []
        people = []
        credentials = []
        for index, (name, nick, mmr, role, schedule, heroes, bio) in enumerate(PLAYERS):
            username = f'demo_vetmo_{index + 1}'
            user, created = get_user_model().objects.get_or_create(username=username, defaults={'email': f'player{index + 1}@example.com', 'first_name': name})
            if created:
                password = secrets.token_urlsafe(18)
                user.set_password(password)
                user.save(update_fields=['password'])
                credentials.append({'username': username, 'password': password})
            users.append(user)
            person = record(f'person{index}', Person, {'account': user}, {
                'name': name, 'nickname': nick, 'mmr': mmr, 'position': role,
                'play_schedule': schedule, 'timezone_name': 'Europe/Moscow', 'favorite_heroes': heroes, 'bio': bio,
                'joined_at': (now - timedelta(days=(184, 142, 91, 116, 168, 73, 35, 22)[index])).date(),
                'status': ('looking', 'looking', 'looking', 'busy', 'looking', 'busy', 'looking', 'training')[index],
                'goal': ('team', 'rating', 'fun', 'team', 'team', 'rating', 'fun', 'team')[index],
                'play_days': (['0', '1', '2', '3', '4'], ['1', '3', '5'], ['5', '6'], ['0', '1', '2', '3', '4', '5', '6'], ['0', '2', '4'], ['0', '1', '2', '3', '4', '5', '6'], ['5', '6'], ['0', '1', '2', '3', '4'])[index],
                'play_from': time((20, 21, 16, 19, 20, 22, 18, 19)[index], (0, 0, 0, 30, 0, 0, 0, 0)[index]),
                'play_until': time((23, 23, 22, 23, 23, 1, 22, 22)[index], (30, 30, 0, 0, 0, 0, 0, 0)[index]),
            })
            people.append(person)
            achievement = record('achievement', Achievement, {'title': 'Первый микс'}, {
                'title': 'Первый микс', 'description': 'Сыграл первую встречу полным составом'}, {'title': '[демо] Свои на карте'})
            record(f'award{index}', PlayerAchievement, {'person': person, 'achievement': achievement}, {
                'awarded_at': (now - timedelta(days=(164, 126, 77, 98, 154, 59, 21, 8)[index])).date()})

        publications = (
            ('news', 'Микс в пятницу — собираемся к 20:30', 'Сначала две обычки, дальше решим по составу.', 'В пятницу собираемся в голосовом к 20:20. Начало первой карты в 20:30 по Москве.\n\nЗапишитесь в событиях и укажите контакт. Если планы поменяются, отмените запись — место перейдёт следующему в очереди.\n\nПервые две карты играем разными составами. Рейтинг оставим на потом.'),
            ('diary', 'Пять в смоке, четыре по плану', 'Как один TP превратил хороший выход в прогулку по реке.', 'На первой карте kiyo показался внизу, стянул двоих и ушёл через Orb. Пока соперник искал Puck, sayro с командой забрал Рошана. Получилось ровно то, о чём договорились до выхода.\n\nНа второй нажали смок раньше, чем наш Mars закончил телепорт на нижнюю линию. Вчетвером дошли до реки, увидели Centaur и вспомнили, что начинать драку вообще-то некому. Развернулись без потерь. Уже неплохой результат для этого колла.\n\nНа следующий вечер договорились: перед смоком проверяем TP и готовность блинка. Фраза «все здесь?» теперь требует ответа.'),
            ('news', 'Вечерний кап: открываем регистрацию', 'Пять игроков, один капитан и вечер на игры до двух побед.', 'После Осеннего капа собираем следующий турнир. Заявку оставляет капитан: название команды и пять игроков с позициями. Точные даты старта и окончания регистрации указаны на странице «Вечерний кап».\n\nИграем полуфиналы и финал до двух побед. Замены согласуем до первой карты, время встреч — с капитанами после закрытия заявок.\n\nПока принимаем составы. Сетка появится после регистрации: заранее назначать себе удобного соперника не получится.'),
            ('diary', 'Отошли от трона. Трон никуда не делся', 'Одна удачная пауза между выигранной дракой и заходом на базу.', 'На 35-й забрали вторую сторону. У Luna оставалось меньше минуты Aegis, у Oracle — ни ульта, ни выкупа. sayro уже бил следующую башню, но диспетчер попросил отойти до своего кулдауна. На удивление, отошли.\n\nsae оставил вард на выходе из базы. Через две минуты под ним поймали Lion, забрали следующую волну и закончили впятером. Керри соперника выкупился, но уже без контроля не смог добраться до Luna.\n\nВ реплее этот момент выглядит скучно: стоим, фармим, ждём. В истории матчей — зелёным. Нас устраивает.'),
        )
        old_titles = ('Открываем сезон дружеских игр', 'Как мы научились слышать коллы', 'Турнир пяти позиций', 'Разбираем камбэк на последней минуте')
        for index, (kind, title, summary, body) in enumerate(publications):
            record(f'post{index}', Publication, {'title': title}, {'title': title, 'kind': kind, 'summary': summary, 'body': body, 'is_published': True, 'published_at': now - timedelta(days=index + 1)}, {'title': f'[демо] {old_titles[index]}'})

        # удаляем только товары из прежней отдельной коллекции
        old_category = Category.objects.filter(name='[демо] коллекция', category='Демонстрационный мерч').first()
        if old_category:
            Product.objects.filter(cat_id=old_category, name__in=['[демо] Футболка команды', '[демо] Худи саппорта', '[демо] Кепка капитана']).delete()
            if not old_category.products.exists():
                old_category.delete()

        friday = (now + timedelta(days=(4 - now.weekday()) % 7)).replace(hour=17, minute=30, second=0, microsecond=0)
        if friday <= now:
            friday += timedelta(days=7)
        event = record('event0', GuildEvent, {'title': 'Пятничный микс'}, {'title': 'Пятничный микс', 'description': 'Старт в 20:30 МСК, голосовой открываем в 20:20. Играем две обычки, между картами меняем линии и составы. Три открытых места в первой пятёрке, ещё два игрока уже подтвердились у капитана; следующие заявки идут в резерв. Если не успеваете, отмените запись: лучше замена за полчаса, чем четыре человека в лобби.', 'starts_at': friday, 'capacity': 3}, {'title': '[демо] Вечер полных составов'})
        for index, user in enumerate(users[:5]):
            record(f'reg{index}', EventRegistration, {'event': event, 'account': user}, {'nickname': PLAYERS[index][1], 'contact': f'Discord: {PLAYERS[index][1]}', 'is_waiting': index >= 3, 'visitor_key': f'demo-event-{index}'})
        record('event1', GuildEvent, {'title': 'Разбор реплея: первые десять минут'}, {'title': 'Разбор реплея: первые десять минут', 'description': 'sae и сын катапульты покажут одну и ту же линию глазами четвёрки и тройки. Поставим паузу перед отводом, руной на шестой и первым уходом с линии: что видели тогда и что стоило проверить. Около 40 минут, вопросы по ходу. Свой реплей можно предложить в чате — особенно если непонятно, где именно закончилась хорошая линия.', 'starts_at': now + timedelta(days=5), 'capacity': 10}, {'title': '[демо] Школа поддержки'})
        for index, (title, description, days) in enumerate((
            ('Микс: меняем линии', 'Сыграли две карты. Во второй поменяли пары на боковых линиях: sae попробовал лайнинг с гречей, а диспетчер помог сыну катапульты забрать раннюю башню. По итогам оставили прежние роли, но повторим такой формат через неделю.', 9),
            ('Вечер реплеев: куда пропал наш лес', 'Разобрали поражение после двух потерянных внешних башен. Нашли лишний TP пятёрки и уход четвёрки под вражескую катапульту. На следующем миксе заранее выбираем, какую сторону карты защищать.', 6),
        )):
            past = record(f'past-event{index}', GuildEvent, {'title': title}, {'title': title, 'description': description,
                'starts_at': now - timedelta(days=days), 'ends_at': now - timedelta(days=days) + timedelta(hours=2), 'capacity': 10})
            for member_index in range(5):
                record(f'past-reg{index}-{member_index}', EventRegistration, {'event': past, 'account': users[member_index]},
                    {'nickname': PLAYERS[member_index][1], 'contact': f'Discord: {PLAYERS[member_index][1]}', 'is_waiting': False})

        for index, user in enumerate(users[:3]):
            listing = record(f'party{index}', PartyListing, {'account': user, 'visitor_key': f'demo-party-{index}'}, {
                'nickname': PLAYERS[index][1], 'captain_role': PLAYERS[index][3], 'role': ('Полная поддержка / 5', 'Керри / 1', 'Мид / 2')[index],
                'mmr_min': (2800, 3500, 2200)[index], 'mmr_max': (4000, 4800, 3400)[index], 'schedule': PLAYERS[index][4],
                'mode': ('Рейтинг', 'Рейтинг', 'Обычная')[index], 'goal': ('rating', 'rating', 'fun')[index],
                'contact': f'Discord: {PLAYERS[index][1]}', 'expires_at': now + timedelta(days=6)})
            for member_index in (3, 4):
                record(f'response{index}-{member_index}', PartyResponse, {'listing': listing, 'visitor_key': f'demo-response-{member_index}'}, {
                    'account': users[member_index], 'nickname': PLAYERS[member_index][1], 'role': PLAYERS[member_index][3],
                    'contact': f'Discord: {PLAYERS[member_index][1]}', 'message': ('После 19:30 буду, могу две или три карты.', 'Могу на пятёрке. Только без старта в полночь, завтра вставать.')[member_index - 3], 'is_accepted': member_index == 3})
            record(f'notice{index}', Notification, {'account': user, 'text': f'{PLAYERS[4][1]} откликнулся на твоё объявление'}, {'text': f'{PLAYERS[4][1]} откликнулся на твоё объявление', 'url': f'/party/{listing.pk}/'}, {'account': user, 'text': '[демо] На твоё объявление пришёл отклик'})
        Favorite.objects.get_or_create(account=users[0], person=Person.objects.get(account=users[1]))
        record('recruitment', FormResult, {'account': users[0], 'myname': PLAYERS[0][1]}, {'myname': PLAYERS[0][1], 'gender': 'Керри / 1', 'step': PLAYERS[0][2], 'status': 'review', 'play_schedule': PLAYERS[0][4]}, {'account': users[0], 'myname': '[демо] Заявка Кедра'})

        reports = []
        for index, (title, score, analysis) in enumerate((
            ('Второй Рошан: дождались BKB и забрали карту', '38 : 27', 'До BKB sayro на Luna дважды терял половину здоровья ещё до начала драки. На следующем выходе сын катапульты не стал прыгать в первого показавшегося героя: подождал, пока sae снимет вражеский вард, и дал Arena на подходе к реке. Luna смогла бить внутри драки, а не отходить от неё.\n\nkiyo на Puck держал второй вход и не пустил саппортов к яме. После Рошана забрали внешнюю башню и только затем пошли на базу.\n\nЧто повторить: проверка обзора перед входом, один голос на начало драки. Что поправить: на первом Рошане диспетчер остался один снаружи ямы — Oracle нужен путь отхода, а не только хороший обзор.'),
            ('Три башни, ни одного решения', '22 : 41', 'К десятой минуте линии были ровными. Затем sae ушёл помогать миду без отпушенной сложной, Mars остался под катапультой один, а TP диспетчера уже был потрачен на сейв керри. За следующие пять минут отдали две внешние башни без размена.\n\nСмок на 18-й нажали из своего треугольника без информации о вражеском керри. Нашли танка, потратили Arena и Dream Coil, а урон Luna пришёл уже после ответных кнопок.\n\nНа следующую карту: заранее выбрать башню, которую защищаем втроём. Если не успеваем — отпускаем и забираем противоположную линию. Покупка смока сама по себе планом пока не считается.'),
            ('Oracle выкупился, Luna осталась жить', '46 : 39', 'На 43-й минуте диспетчер погиб первым: вард на возвышенности пережил наш сентри и показал подход Oracle. Выкупился сразу, телепортировался на базу и успел дать False Promise на отходящую Luna. sayro сохранил Satanic до окончания контроля и вернулся в драку уже после сейва.\n\nВыиграли размен, но без выкупа на пятёрке не стали форсировать трон. sae проверил выходы, kiyo протолкнул середину, а Mars сохранил Arena для следующего захода. Закончили через нижнюю линию.\n\nГлавный вывод: после выкупа называем точку TP голосом. В этой игре успели; повторять проверку на скорость реакции не хочется.'),
        )):
            report = record(f'match{index}', MatchReport, {'title': title}, {'title': title, 'played_at': now - timedelta(days=(7, 8, 7)[index], hours=(2, 0, 0)[index]), 'won': index != 1, 'score': score, 'roster': '\n'.join(f'{PLAYERS[j][1]} — {hero}' for j, hero in enumerate(('Luna', 'Puck', 'Mars', 'Rubick', 'Oracle'))), 'analysis': analysis}, {'title': f'[демо] Карта {index + 1} против команды Рассвет'})
            if options['refresh'] or not report.players.exists():
                report.players.set(people[:5])
            reports.append(report)
        tournament = record('tournament', Tournament, {'title': 'Осенний кап'}, {'title': 'Осенний кап', 'description': 'Четыре состава, полуфиналы и финал BO3. late queue забрали решающую серию у 5% packet loss со счётом 2:1. Разборы двух карт финала — ниже, вместе с составами.', 'starts_at': now - timedelta(days=8), 'registration_ends_at': now - timedelta(days=10)}, {'title': '[демо] Кубок своих'})
        teams = []
        team_nicks = (tuple(player[1] for player in PLAYERS[:5]), ('греча', 'velto', 'raize', 'на две', 'sova'), ('kaien', 'не тот акк', 'deimos', 'курьер пешком', 'fey'), ('r1vo', 'seiren', 'кабан', 'mello', 'без прерола'))
        captains = [users[0], users[5]]
        for index, nickname in ((3, 'kaien'), (4, 'r1vo')):
            captain, created = get_user_model().objects.get_or_create(username=f'demo_vetmo_captain_{index}', defaults={'first_name': nickname})
            if created:
                captain.set_unusable_password()
                captain.save(update_fields=['password'])
            captains.append(captain)
        for index, name in enumerate(('late queue', 'без разогрева', '5% packet loss', 'ещё не всё')):
            team = record(f'team{index}', TournamentTeam, {'tournament': tournament, 'name': name}, {'name': name, 'captain': captains[index], 'roster': '\n'.join(f'{nick} — позиция {j + 1}' for j, nick in enumerate(team_nicks[index]))})
            if options['refresh'] or not team.players.exists():
                team.players.set(people[:5] if index == 0 else (people[5:] if index == 1 else []))
            teams.append(team)
        for a, b in ((0, 1), (2, 3)):
            record(f'semifinal{a}', TournamentMatch, {'tournament': tournament, 'round': 1, 'team_a': teams[a], 'team_b': teams[b]},
                {'score_a': 2, 'score_b': 1 if a == 0 else 0, 'is_finished': True, 'starts_at': now - timedelta(days=8)})
        final = record('final', TournamentMatch, {'tournament': tournament, 'round': 2, 'team_a': teams[0], 'team_b': teams[2]},
            {'score_a': 2, 'score_b': 1, 'is_finished': True, 'starts_at': now - timedelta(days=7, hours=3)})
        if options['refresh']:
            for report, match in ((reports[0], final), (reports[1], tournament.matches.get(round=1, team_a=teams[0])), (reports[2], final)):
                report.tournament_match = match
                report.save(update_fields=['tournament_match'])
        else:
            MatchReport.objects.filter(pk__in=[reports[0].pk, reports[2].pk], tournament_match__isnull=True).update(tournament_match=final)

        current = record('current-tournament', Tournament, {'title': 'Кубок буднего вечера'}, {'title': 'Кубок буднего вечера',
            'description': 'Мини-кап на четыре команды. Полуфиналы уже сыграны: late queue и без разогрева встретятся в финале BO3. Начало серии указано в сетке, капитаны подтвердили составы.',
            'starts_at': now - timedelta(days=1), 'registration_ends_at': now - timedelta(days=3)})
        current_teams = []
        for index, name in enumerate(('late queue', 'без разогрева', '5% packet loss', 'ещё не всё')):
            team = record(f'current-team{index}', TournamentTeam, {'tournament': current, 'name': name},
                {'name': name, 'captain': captains[index], 'roster': '\n'.join(f'{nick} — позиция {j + 1}' for j, nick in enumerate(team_nicks[index]))})
            if options['refresh'] or not team.players.exists():
                team.players.set(people[:5] if index == 0 else (people[5:] if index == 1 else []))
            current_teams.append(team)
        for a, b in ((0, 2), (1, 3)):
            record(f'current-semi{a}', TournamentMatch, {'tournament': current, 'round': 1, 'team_a': current_teams[a], 'team_b': current_teams[b]},
                {'score_a': 2, 'score_b': 1, 'is_finished': True, 'starts_at': now - timedelta(days=1)})
        record('current-final', TournamentMatch, {'tournament': current, 'round': 2, 'team_a': current_teams[0], 'team_b': current_teams[1]},
            {'score_a': 0, 'score_b': 0, 'is_finished': False, 'starts_at': now + timedelta(days=1)})

        upcoming = record('upcoming-tournament', Tournament, {'title': 'Вечерний кап'}, {'title': 'Вечерний кап',
            'description': 'Открытая регистрация составов гильдии. Полуфиналы и финал BO3; жеребьёвка после закрытия заявок. Капитан указывает пять ников с позициями, замены согласует до первой карты.',
            'starts_at': now + timedelta(days=10), 'registration_ends_at': now + timedelta(days=7)})
        for index in (0, 1):
            team = record(f'upcoming-team{index}', TournamentTeam, {'tournament': upcoming, 'name': teams[index].name},
                {'name': teams[index].name, 'captain': captains[index], 'roster': teams[index].roster})
            if options['refresh'] or not team.players.exists():
                team.players.set(people[:5] if index == 0 else people[5:])

        extra = record('match-late-stack', MatchReport, {'title': 'Поменяли линии, сохранили темп'}, {
            'title': 'Поменяли линии, сохранили темп', 'played_at': now - timedelta(days=9) + timedelta(hours=1),
            'won': True, 'score': '31 : 24', 'roster': '\n'.join(f'{people[j].nickname} — {hero}' for j, hero in zip((5, 7, 2, 3, 4), ('Sven', 'Leshrac', 'Underlord', 'Tusk', 'Jakiro'))),
            'analysis': 'греча на Sven закончил линию без смертей, но к первому выходу не хватало пары сотен до BKB. Не стали проверять, насколько это важный предмет: отпушили две линии и подождали следующую волну.\n\nvelto на Leshrac занял мид, sae с Tusk сыграл рядом и остановил ответный заход. Underlord перенёс команду на нижнюю линию после драки — забрали башню до возрождения соперника.\n\nНа следующую игру: заранее оставлять стаки для Sven и не тратить обе поддержки на одну руну.'})
        if options['refresh'] or not extra.players.exists():
            extra.players.set(people[j] for j in (5, 7, 2, 3, 4))
        for key, title, description, member_indexes in (
            ('cup-award', 'Осенний кап — первое место', 'Победа в финале BO3 со счётом 2:1 в составе late queue.', range(5)),
            ('replay-award', 'Вторая пара глаз', 'Помог провести разбор линии и первых перемещений на вечере реплеев.', (2, 3)),
        ):
            achievement = record(key, Achievement, {'title': title}, {'title': title, 'description': description})
            for member_index in member_indexes:
                record(f'{key}-{member_index}', PlayerAchievement, {'person': people[member_index], 'achievement': achievement},
                    {'awarded_at': (now - timedelta(days=7 if key == 'cup-award' else 6)).date()})

        for index, (title, choices) in enumerate((('Когда собираем следующий микс?', ('Пятница 20:30', 'Суббота 18:00', 'Воскресенье 19:00')), ('Что разбираем на следующей встрече?', ('Линию и первые перемещения', 'Драки за Рошана', 'Как заходить на базу без приключений')))):
            old = ('Когда играем следующий микс', 'Какой мерч выпустить')[index]
            poll = record(f'poll{index}', Poll, {'title': title}, {'title': title, 'closes_at': now + timedelta(days=4)}, {'title': f'[демо] {old}'})
            old_options = list(poll.choices.order_by('pk'))
            options_list = []
            for j, text in enumerate(choices):
                choice = record(f'choice{index}-{j}', PollChoice, {'poll': poll, 'text': text}, {'text': text}, {'pk': old_options[j].pk} if j < len(old_options) else None)
                options_list.append(choice)
            for j, user in enumerate(users[1:]):
                PollVote.objects.get_or_create(poll=poll, account=user, defaults={'choice': options_list[(j + index) % 3]})

        order_id = uuid.uuid5(uuid.NAMESPACE_URL, 'vetmo-demo-order-v1')
        order = record('order', MerchOrder, {'pk': order_id}, {'account': users[0], 'name': PLAYERS[0][0], 'contact': f'Discord: {PLAYERS[0][1]}', 'delivery': 'Казань, пункт выдачи', 'comment': 'Лучше написать в дискорд, днём могу не ответить'})
        # в истории сохраняем покупку даже если товар убран из каталога
        item = order.items.first()
        if item and options['refresh']:
            item.name = 'Футболка vetmo'
            item.save(update_fields=['name'])
        elif item is None:
            MerchOrderItem.objects.create(order=order, name='Футболка vetmo', size='M', quantity=1, price=1500)
        if credentials:
            credentials_path = folder / 'demo_accounts.json'
            existing = json.loads(credentials_path.read_text(encoding='utf-8')) if credentials_path.exists() else []
            credentials_path.write_text(json.dumps(existing + credentials, ensure_ascii=False, indent=2), encoding='utf-8')
        path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS('Данные для показа готовы доступы сохранены в .local/demo_accounts.json'))
