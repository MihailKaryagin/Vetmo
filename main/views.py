# Как читать этот файл: браузер запрашивает адрес → main/urls.py выбирает функцию
# (view) → функция читает request, обращается к моделям и возвращает HTTP-ответ.
# request.GET — параметры после «?» в адресе; request.POST — поля отправленной формы.
# request.user — посетитель, request.session — данные между его запросами.
# render(request, 'main/news.html', {'page_obj': page}) подставляет page в шаблон
# под именем page_obj и возвращает браузеру HTML. Файл шаблона лежит в main/templates/.
# redirect('account') возвращает адрес перехода: браузер сам делает новый GET.
# reverse('account') только строит строку адреса по имени маршрута из urls.py.
# Делим выдачу на страницы с помощью Paginator.
from django.core.paginator import Paginator
# reverse строит URL по имени маршрута из urls.py.
from django.urls import reverse
# Импортируем поиск объекта с ответом 404, перенаправление и вывод HTML-шаблона.
from django.shortcuts import get_object_or_404, redirect, render
# messages сохраняет короткое уведомление для показа посетителю.
from django.contrib import messages
# login связывает аккаунт с текущей сессией после регистрации.
from django.contrib.auth import login
# Декоратор login_required проверяет вход перед вызовом обработчика.
from django.contrib.auth.decorators import login_required
# Стандартная форма создания пользователя Django; напрямую ниже не используется.
from django.contrib.auth.forms import UserCreationForm
# Наша форма регистрации описывает поля и проверяет введённые данные.
from .forms import SignupForm
# Декоратор проекта ограничивает частоту отправки форм методом POST.
from .services import limit_posts
# Помощники сравнивают расписания, объясняют подбор и определяют открытые позиции.
from .scheduling import overlap_reason, party_reasons, recruiting_roles
# Q превращает условие поиска в объект: условия можно соединять через | (ИЛИ).
from django.db.models import Q
# timezone даёт время с учётом настроек часовых поясов Django.
from django.utils import timezone
# transaction позволяет объединить несколько изменений базы в одну операцию.
from django.db import transaction
# require_POST отклоняет обращения другими методами, например GET.
from django.views.decorators.http import require_POST
# HttpResponseForbidden создаёт готовый HTTP-ответ со статусом 403.
from django.http import HttpResponseForbidden
# Формы проекта: проверяют данные анкеты, объявления, заказа, профиля и фильтров.
from .forms import RecruitmentForm, PartyForm, EventRegistrationForm, PartyResponseForm, OrderForm, PlayerFilterForm, ProfileForm, PartyFilterForm, EmailChangeForm
# Модели описывают записи в базе: товары, игроков, события, отклики и другие сущности.
from .models import Product, Category, Person, FormResult, Publication, GuildEvent, EventRegistration, PartyListing, PartyResponse, MerchOrder, MerchOrderItem, ProductVariant, Notification, MatchReport, TournamentMatch
# uuid нужен для случайного идентификатора гостевой сессии.
import uuid
# hashlib вычисляет отпечаток данных, чтобы распознать повторную отправку.
import hashlib
# Здесь подключаем подбор объявлений и поиск ближайших игр пользователя.
from .guild import search_parties, upcoming_games
# Case и When задают условия в SQL, Count считает строки, F ссылается на поле записи.
from django.db.models import Case, Count, When, F
# timedelta — промежуток времени, например один час или один день.
from datetime import timedelta


# Функция получает запрос и возвращает постоянный для этой сессии ключ гостя.
def visitor_key(request):
    # Случайный ключ связывает гостевые объявления и записи с этой сессией до входа.
    # Если ключ ещё не записали, его нужно создать.
    if 'community_key' not in request.session:
        # uuid4 создаёт случайный UUID; .hex превращает его в строку без дефисов.
        request.session['community_key'] = uuid.uuid4().hex
    # Возвращаем уже сохранённый ключ, в том числе при повторном визите.
    return request.session['community_key']


# Проверяем, вправе ли посетитель управлять конкретным объявлением.
def owns_listing(request, listing):
    # после привязки к аккаунту управление доступно только владельцу аккаунта
    # У объявления есть владелец-аккаунт? Тогда гостевой ключ не используем.
    if listing.account_id:
        # Оба условия должны выполниться: посетитель вошёл и его ID совпал с ID владельца.
        return request.user.is_authenticated and listing.account_id == request.user.pk
    # Для гостевого объявления нужен непустой ключ, совпадающий с ключом сессии.
    return bool(listing.visitor_key and listing.visitor_key == request.session.get('community_key'))


# Ограничиваем частоту отправки регистрационной формы.
@limit_posts
# Обрабатываем страницу регистрации; request содержит данные обращения браузера.
def signup(request):
    # GET /account/signup/ показывает пустую форму. POST передаёт поля в SignupForm;
    # is_valid() проверяет их. При ошибке тот же шаблон получит форму с ошибками.
    # Если посетитель уже вошёл, создавать ещё один аккаунт здесь не нужно.
    if request.user.is_authenticated:
        # Возвращаем перенаправление на URL кабинета; браузер сделает новый запрос.
        return redirect('account')
    # При POST передаём введённые поля, а при GET — None, чтобы показать пустую форму.
    form = SignupForm(request.POST if request.method == 'POST' else None)
    # Сохранять пользователя можно только после отправки и успешной проверки полей.
    if request.method == 'POST' and form.is_valid():
        # Создаём в базе аккаунт и получаем объект пользователя.
        user = form.save()
        # Выполняем вход: следующий запрос из этой сессии уже будет от имени user.
        login(request, user)
        # После регистрации открываем кабинет, а не повторяем отправку формы.
        return redirect('account')
    # При GET или ошибке передаём форму в signup.html; ошибки остаются в объекте form.
    return render(request, 'registration/signup.html', {'form': form})


# Гостю вместо кабинета будет предложено войти.
@login_required
# Показываем кабинет; email_form может прийти из обработчика смены почты с ошибками.
def account(request, email_form=None):
    # Value передаёт константу, When описывает условие, Case выбирает значение по условиям.
    from django.db.models import Case, When, Value
    # Общий префикс помогает распознать уведомления о подтверждении игры.
    from .community import CONFIRM_PREFIX
    # переносим только гостевые записи из текущего браузера
    # Читаем ключ гостя, если он уже был создан в этом браузере.
    key = request.session.get('community_key')
    # Перенос гостевых записей имеет смысл только при наличии ключа.
    if key:
        # __isnull=True означает «поле в базе пустое». update меняет все найденные строки.
        # exclude(...__in=existing_ids) пропускает пати, где уже есть отклик этого аккаунта.
        # Назначаем пользователя владельцем его гостевых объявлений без аккаунта.
        PartyListing.objects.filter(visitor_key=key, account__isnull=True).update(account=request.user)
        # flat=True возвращает сами ID объявлений; list загружает их до следующего UPDATE.
        existing_ids = list(PartyResponse.objects.filter(account=request.user).values_list('listing_id', flat=True))
        # Привязываем гостевые отклики, исключая пати, где аккаунт уже откликался.
        PartyResponse.objects.filter(visitor_key=key, account__isnull=True).exclude(listing_id__in=existing_ids).update(account=request.user)
        # Таким же образом привязываем гостевые регистрации на события.
        EventRegistration.objects.filter(visitor_key=key, account__isnull=True).update(account=request.user)
    # Из сессии узнаём номер последнего заказа, сделанного в этом браузере.
    last_order = request.session.get('last_merch_order')
    # Если номер известен, можно попытаться привязать заказ.
    if last_order:
        # Обновляем только указанный заказ и только если у него ещё нет владельца.
        MerchOrder.objects.filter(pk=last_order, account__isnull=True).update(account=request.user)
    # get_or_create возвращает пару (объект, создан ли он сейчас); флаг здесь не нужен (_).
    # instance=profile привязывает форму к существующему профилю для редактирования.
    # Получаем профиль или создаём его; начальное имя ограничено 20 символами.
    profile, _ = Person.objects.get_or_create(account=request.user, defaults={'name': request.user.username[:20]})
    # instance указывает, какой профиль редактировать; поля смены почты в него не попадают.
    form = ProfileForm(request.POST if request.method == 'POST' and email_form is None else None, instance=profile)
    # Обрабатываем только корректную отправку формы профиля, а не формы почты.
    if request.method == 'POST' and email_form is None and form.is_valid():
        # Записываем проверенные изменения профиля в базу.
        form.save()
        # Сохраняем сообщение, которое покажет шаблон после перехода.
        messages.success(request, 'Профиль сохранён')
        # Заново открываем кабинет методом GET с обновлёнными данными.
        return redirect('account')
    # Собираем предстоящие игры, в состав которых приняли пользователя.
    games = list(upcoming_games(request.user))
    # Для каждой игры готовим время, подпись по статусу подтверждения и адрес её карточки.
    agenda = [{'at': g.listing.game_at, 'title': ('Игра: ' if g.confirmed_at else 'Подтвердить участие: ') + g.listing.nickname, 'url': reverse('party_detail', args=[g.listing_id])} for g in games]
    # Отдельно находим будущие активные игры пользователя в роли капитана.
    for listing in PartyListing.objects.filter(account=request.user, is_active=True, game_at__gt=timezone.now()):
        # Добавляем капитанскую игру в тот же список дел.
        agenda.append({'at': listing.game_at, 'title': 'Ты капитан: ' + listing.nickname, 'url': reverse('party_detail', args=[listing.pk])})
    # listing__account: от отклика переходим по связи listing к владельцу объявления.
    # values(...).annotate(total=Count('pk')) группирует строки по объявлению и считает отклики.
    # Ищем отклики на активные объявления текущего капитана.
    pending = PartyResponse.objects.filter(listing__account=request.user, listing__is_active=True,
        # Набор ещё идёт, отклик не принят и не снят; values выбирает нужные столбцы.
        listing__expires_at__gt=timezone.now(), is_accepted=False, removed_at=None).values(
        # Группируем по объявлению и считаем отклики; пустой order_by снимает сортировку модели.
        'listing_id', 'listing__nickname', 'listing__expires_at').annotate(total=Count('pk')).order_by()
    # Перебираем полученные группы: одна строка результата на объявление.
    for row in pending:
        # Добавляем капитану задачу со сроком окончания набора и числом ожидающих откликов.
        agenda.append({'at': row['listing__expires_at'], 'title': f"До конца набора: рассмотреть отклики ({row['total']}) · {row['listing__nickname']}", 'url': reverse('party_detail', args=[row['listing_id']])})
    # Строим адреса только тех игр, где участник ещё не подтвердил время.
    confirm_urls = [reverse('party_detail', args=[g.listing_id]) for g in games if not g.confirmed_at]
    # Case/When вычисляет приоритет уведомления прямо в запросе. Минус в '-urgency'
    # сортирует по убыванию, поэтому просьба подтвердить игру окажется выше новости.
    # annotate добавляет каждому уведомлению вычисляемый атрибут urgency без записи в базу.
    notices = request.user.notifications.annotate(
        # Действующая просьба о подтверждении получает наивысший приоритет 2.
        urgency=Case(When(text__startswith=CONFIRM_PREFIX, url__in=confirm_urls, then=Value(2)),
                     # Непрочитанным откликам ставим 1, всем остальным уведомлениям — 0.
                     When(text__startswith='Отклики · ', is_read=False, then=Value(1)), default=Value(0)))
    # Берём до 50 уведомлений: сначала срочные, затем непрочитанные, внутри — новые.
    notices = list(notices.order_by('-urgency', 'is_read', '-created_at', '-pk')[:50])
    # Проверяем текст каждого выбранного уведомления перед показом.
    for notice in notices:
        # Если старый призыв уже не требует действия, текст стоит уточнить.
        if not notice.urgency and notice.text.startswith(CONFIRM_PREFIX):
            # Меняем подпись для этой страницы; без save() запись в базе не меняется.
            notice.text = 'Ранее была назначена игра. Подтверждение больше не требуется.'
    # Выбираем регистрации на будущие опубликованные события без отмены и загружаем сами события.
    for reg in EventRegistration.objects.filter(account=request.user, event__is_published=True, event__is_cancelled=False, event__starts_at__gte=timezone.now()).select_related('event'):
        # Добавляем время, статус очереди и ссылку с якорем на карточку события.
        agenda.append({'at': reg.event.starts_at, 'title': ('Очередь: ' if reg.is_waiting else 'Событие: ') + reg.event.title, 'url': reverse('events') + f'#event-{reg.event_id}'})
    # Отдаём шаблону кабинета словарь ниже; его ключи станут переменными шаблона.
    return render(request, 'main/account.html', {
        # sorted упорядочивает события и игры по общему полю времени at.
        'agenda': sorted(agenda, key=lambda item: item['at']),
        # Шаблон получит редактируемую форму и сам профиль отдельно.
        'form': form, 'profile': profile,
        # Передаём текущее время для сравнений в шаблоне.
        'now': timezone.now(),
        # Сохраняем ошибочную форму почты или подставляем текущий email в новую форму.
        'email_form': email_form if email_form is not None else EmailChangeForm(initial={'email': request.user.email}),
        # Передаём объявления, созданные вошедшим пользователем.
        'listings': PartyListing.objects.filter(account=request.user),
        # Передаём его регистрации вместе со связанными событиями.
        'registrations': EventRegistration.objects.filter(account=request.user).select_related('event'),
        # Загружаем заказы пользователя и заранее получаем их позиции.
        'orders': MerchOrder.objects.filter(account=request.user).prefetch_related('items'),
        # Анкеты на вступление сортируем от большего ID к меньшему.
        'recruitments': FormResult.objects.filter(account=request.user).order_by('-pk'),
        # Под ключом notifications доступны подготовленные и отсортированные уведомления.
        'notifications': notices,
        # История откликов: сначала новые; объявление каждого отклика загружается вместе с ним.
        'my_responses': PartyResponse.objects.filter(account=request.user).select_related('listing').order_by('-created_at'),
        # Берём до пяти опубликованных разборов профиля с датой не позже текущей.
        'my_reports': profile.match_reports.filter(is_published=True, played_at__lte=timezone.now())[:5],
    # Закрываем словарь контекста и вызов render: результатом будет HTML кабинета.
    })


# Отмечать уведомления может только вошедший пользователь.
@login_required
# Переход по обычной ссылке GET не должен менять статус уведомлений.
@require_POST
# Обрабатываем кнопку «Отметить прочитанными».
def notifications_read(request):
    # @login_required требует входа; @require_POST разрешает изменение только через POST.
    # Меняем уведомления текущего пользователя и возвращаем его в кабинет.
    # Одним UPDATE ставим флаг только у непрочитанных уведомлений этого пользователя.
    request.user.notifications.filter(is_read=False).update(is_read=True)
    # Открываем кабинет снова, теперь уже с обновлёнными статусами.
    return redirect('account')


# Формируем главную страницу сайта.
def index(request):
    # Для главной собираем данные нескольких разделов. count() даёт число записей,
    # first() — один объект или None, [:3] ограничивает выборку тремя записями.
    # getattr берёт профиль посетителя или возвращает None, если профиля нет.
    viewer = getattr(request.user, 'player_profile', None)
    # Просим подборщик найти рекомендации без явно заданных фильтров поиска.
    candidates = search_parties({}, viewer, timezone.now(), recommend=True, request=request)
    # Проверяем, что список не пуст, прежде чем брать элемент с индексом 0.
    if candidates:
        # Добавляем лучшему кандидату пояснения: почему он подходит этому игроку.
        candidates[0].reasons = party_reasons(viewer, candidates[0])
    # На главной можно показывать только активные публичные профили.
    people = Person.objects.filter(is_active=True, is_public=True)
    # Начинаем словарь счётчиков для блока статистики.
    stats = {
        # Считаем видимые профили, не загружая объекты игроков ради подсчёта.
        "people_count": Person.objects.filter(is_active=True, is_public=True).count(),
        # Считаем опубликованные, не отменённые события с началом не раньше текущего момента.
        "events_count": GuildEvent.objects.filter(is_published=True, is_cancelled=False, starts_at__gte=timezone.now()).count(),
        # Считаем действующие объявления, у которых срок набора ещё не истёк.
        "party_count": PartyListing.objects.filter(is_active=True, expires_at__gt=timezone.now()).count(),
        # Считаем публикации, которые уже разрешено показывать.
        "published_count": Publication.objects.published().count(),
    # Эти четыре значения образуют словарь stats.
    }
    # Передаём главной странице данные для отдельных блоков.
    return render(request, 'main/index.html', {
        # Срез [:6] берёт максимум шесть профилей; stats содержит общие показатели.
        'people': people[:6], 'stats': stats,
        # В карточку попадёт первый кандидат либо None для пустого состояния.
        'recommended': candidates[0] if candidates else None,
        # Для вошедшего берём первую предстоящую игру до следующей местной полуночи.
        'next_game': upcoming_games(request.user).filter(listing__game_at__lt=timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).first() if request.user.is_authenticated else None,
        # Показываем до трёх видимых публикаций типа «Новости».
        'latest_news': Publication.objects.published().filter(kind=Publication.Kind.NEWS)[:3],
        # Находим первую подходящую встречу; first() вернёт None, если встреч нет.
        'upcoming_event': GuildEvent.objects.filter(is_published=True, is_cancelled=False, starts_at__gte=timezone.now()).first(),
        # Передаём до трёх объявлений с открытым набором.
        'active_parties': PartyListing.objects.filter(is_active=True, expires_at__gt=timezone.now())[:3],
        # Берём первый опубликованный разбор уже сыгранного матча.
        'latest_report': MatchReport.objects.filter(is_published=True, played_at__lte=timezone.now()).first(),
        # Ищем незавершённые матчи видимых турниров.
        'next_match': TournamentMatch.objects.filter(tournament__is_published=True, is_finished=False,
            # Оставляем предстоящие; загружаем турнир и команды и берём ближайший старт.
            starts_at__gte=timezone.now()).select_related('tournament', 'team_a', 'team_b').order_by('starts_at').first(),
    # Заканчиваем подготовку HTML главной страницы.
    })

# Обрабатываем каталог мерча с необязательным фильтром сезона.
def store(request):
    # select_related получает категорию вместе с товаром одним SQL-запросом;
    # prefetch_related отдельно загружает размеры сразу для всех выбранных товаров.
    # Готовим выборку всех категорий для шаблона магазина.
    category = Category.objects.all()
    # Вместе с товарами читаем категории; варианты размеров загружаем отдельной выборкой.
    products = Product.objects.select_related("cat_id").prefetch_related('variants')

    # учитываем только известные сезоны
    # Читаем значение после ?season= из адресной строки.
    season = request.GET.get("season")
    # Применяем фильтр только для одного из двух известных сезонов.
    if season in ("зима", "лето"):
        # /store?season=лето → товар → связанная категория cat_id → её поле name.
        # __iexact сравнивает имя целиком без учёта регистра.
        # Через связь cat_id проверяем полное имя категории без учёта регистра.
        products = products.filter(cat_id__name__iexact=season)

    # Собираем данные каталога в один словарь info.
    info = {
        # По ключу category шаблон получит список категорий.
        "category": category,
        # По ключу products шаблон получит товары с учётом выбранного сезона.
        "products": products,
    # Заканчиваем словарь данных каталога.
    }

    # Возвращаем HTML магазина; season нужен шаблону, чтобы отметить выбранный сезон.
    return render(request, "main/store.html", {"info": info,"season": season,})


# Ограничиваем повторные отправки формы покупки.
@limit_posts
# pk приходит из URL и указывает, какой товар заказывают.
def merch_order(request, pk):
    # pk — первичный ключ товара из URL. Если товара нет, Django вернёт страницу 404.
    # Отпечаток полей помогает распознать повторную отправку заказа из этой сессии.
    # Получаем товар по первичному ключу; неизвестный номер даёт 404.
    product = get_object_or_404(Product, pk=pk)
    # Собираем номер товара и отсортированные поля в строку, кодируем в байты и вычисляем SHA-256.
    fingerprint = hashlib.sha256(f'{pk}:{sorted(request.POST.items())}'.encode()).hexdigest()
    # Ищем сведения о предыдущей отправке в этой сессии; {} означает «сведений нет».
    previous = request.session.get('recent_order', {})
    # Проверяем одновременно метод, совпадение отпечатка и интервал меньше минуты.
    if request.method == 'POST' and previous.get('fingerprint') == fingerprint and timezone.now().timestamp() - previous.get('time', 0) < 60:
        # При повторе открываем подтверждение предыдущего заказа.
        return redirect('order_success')
    # Передаём форме сам товар, чтобы она показала его размеры и проверила количество.
    form = OrderForm(request.POST if request.method == 'POST' else None, product=product)
    # Переходим к покупке, только если пришёл POST и форма прошла проверку.
    if request.method == 'POST' and form.is_valid():
        # atomic объединяет операции внутри отступа: при исключении база их откатит.
        with transaction.atomic():
            # Создание заказа и списание остатков — одна транзакция: при исключении
            # база откатит изменения. select_for_update блокирует выбранные строки,
            # чтобы два покупателя одновременно не купили последний размер.
            # Повторно читаем товар с блокировкой строки до конца транзакции.
            product = Product.objects.select_for_update().get(pk=pk)
            # Готовим запрос вариантов товара с блокировкой при чтении.
            variants = ProductVariant.objects.select_for_update().filter(product=product)
            # Выбираем вариант проверенного размера; first вернёт None, если такого нет.
            variant = variants.filter(size=form.cleaned_data['size']).first()
            # Проверяем доступность всего товара и хватает ли общего остатка.
            if not product.nalichie or form.cleaned_data['quantity'] > product.counter:
                # Привязываем ошибку к полю количества, чтобы показать её покупателю.
                form.add_error('quantity', 'Недостаточно товара в наличии.')
            # Если размеры учитываются отдельно, проверяем наличие нужного размера и его остаток.
            elif variants.exists() and (variant is None or variant.stock < form.cleaned_data['quantity']):
                # Добавляем ошибку именно к выбору размера; заказ в этой ветке не оформляется.
                form.add_error('size', 'Недостаточно товара выбранного размера.')
            # Сюда попадаем, когда обе проверки остатков пройдены.
            else:
                # commit=False пока создаёт объект в памяти: добавляем владельца перед save().
                # Создаём объект заказа из формы без немедленной записи в базу.
                order = form.save(commit=False)
                # Проверяем, кто оформляет покупку: вошедший пользователь или гость.
                if request.user.is_authenticated:
                    # Указываем аккаунт владельца заказа для личного кабинета.
                    order.account = request.user
                # Вставляем заказ в базу; теперь на него можно сослаться в позиции заказа.
                order.save()
                # Создаём позицию заказа, связываем с товаром и сохраняем его название на момент
                # покупки.
                MerchOrderItem.objects.create(order=order, product=product, name=product.name,
                    # Фиксируем выбранный размер, количество и текущую цену; sale здесь означает
                    # цену товара.
                    size=form.cleaned_data['size'], quantity=form.cleaned_data['quantity'], price=product.sale)
                # Вычитаем купленное количество из общего остатка в объекте Python.
                product.counter -= form.cleaned_data['quantity']
                # Записываем в базу изменённое поле counter, не перезаписывая остальные поля.
                product.save(update_fields=['counter'])
                # Если у покупки есть отдельный вариант размера, уменьшаем и его остаток.
                if variant:
                    # Вычитаем количество из запаса именно этого размера.
                    variant.stock -= form.cleaned_data['quantity']
                    # Сохраняем новое значение stock у выбранного варианта.
                    variant.save(update_fields=['stock'])
                # Запоминаем UUID заказа строкой, чтобы его могла найти страница подтверждения.
                request.session['last_merch_order'] = str(order.pk)
                # Сохраняем отпечаток и время для распознавания следующей повторной отправки.
                request.session['recent_order'] = {'fingerprint': fingerprint, 'time': timezone.now().timestamp()}
                # Возвращаем адрес страницы подтверждения; браузер откроет её методом GET.
                return redirect('order_success')
    # При GET или ошибке возвращаем карточку с товаром и той же формой.
    return render(request, 'main/product_detail.html', {'product': product, 'form': form})


# Обработчик просмотра одного товара: pk передаёт маршрут карточки.
def product_detail(request, pk):
    # Карточка показывает форму; её action в product_detail.html ведёт в merch_order.
    # Ищем товар для просмотра; неизвестный ключ приводит к 404.
    product = get_object_or_404(Product, pk=pk)
    # Возвращаем карточку с пустой формой заказа, настроенной на этот товар.
    return render(request, 'main/product_detail.html', {'product': product, 'form': OrderForm(product=product)})


# Показываем подтверждение последнего заказа текущей сессии.
def order_success(request):
    # После redirect берём номер последнего заказа из сессии и выводим его позиции.
    # Ищем по ключу из сессии и подгружаем позиции; без подходящего заказа получим 404.
    order = get_object_or_404(MerchOrder.objects.prefetch_related('items'), pk=request.session.get('last_merch_order'))
    # Передаём объект под именем order в шаблон подтверждения.
    return render(request, 'main/order_success.html', {'order': order})


# Формируем каталог игроков с поиском, фильтрами и страницами.
def people_view(request):
    # objects — точка входа в запросы к модели. filter возвращает QuerySet — описание
    # выборки. Можно добавлять условия; сами строки понадобятся при чтении результата.
    # Несколько условий через запятую означают И: профиль и активный, и публичный.
    # Выбираем видимые профили; сначала сортируем по нику, при одинаковом нике — по ID.
    people = Person.objects.filter(is_active=True, is_public=True).order_by('nickname', 'pk')
    # Читаем позицию из URL; если параметра нет, берём пустую строку.
    position = request.GET.get("position", "")
    # q — имя параметра поиска; strip убирает пробелы в начале и конце текста.
    query = request.GET.get("q", "").strip()
    # Не ограничиваем позицию, пока пользователь сам её не выбрал.
    if position:
        # Q(...) описывает одно условие. Оператор | соединяет условия через ИЛИ:
        # подходит либо основная, либо запасная позиция. Сам Q запрос не выполняет.
        # Символ | соединяет два Q: выбранная позиция может быть основной ИЛИ запасной.
        people = people.filter(Q(position=position) | Q(backup_position=position))
    # Пустая строка не запускает поиск по имени.
    if query:
        # Ищем фрагмент в имени ИЛИ нике; __icontains означает вхождение без учёта регистра.
        people = people.filter(Q(name__icontains=query) | Q(nickname__icontains=query))
    # Передаём GET-параметры форме, которая проверяет типы и допустимые значения фильтров.
    filters = PlayerFilterForm(request.GET)
    # Используем дополнительные фильтры только после успешной проверки формы.
    if filters.is_valid():
        # cleaned_data содержит уже проверенные значения формы. __gte — «не меньше»,
        # __lte — «не больше». Обе границы MMR включаются в результат.
        # cleaned_data — словарь проверенных значений: например, MMR здесь уже число.
        data = filters.cleaned_data
        # Проверяем именно на None: нулевой нижний предел тоже допустим.
        if data.get('mmr_min') is not None:
            # __gte означает «больше или равно»: оставляем игроков не ниже указанного MMR.
            people = people.filter(mmr__gte=data['mmr_min'])
        # Если задан верхний предел, применяем вторую границу диапазона.
        if data.get('mmr_max') is not None:
            # __lte означает «меньше или равно»: исключаем слишком высокий MMR.
            people = people.filter(mmr__lte=data['mmr_max'])
        # Проверяем, задан ли текст для поиска по расписанию.
        if data.get('schedule'):
            # Ищем этот фрагмент в описании игрового времени.
            people = people.filter(play_schedule__icontains=data['schedule'])
        # Если посетитель выбрал цель игры, учитываем её.
        if data.get('goal'):
            # Оставляем профили с точно такой же целью.
            people = people.filter(goal=data['goal'])
        # Проверяем, нужно ли ограничить результат по статусу игрока.
        if data.get('status'):
            # Оставляем только игроков с выбранным статусом.
            people = people.filter(status=data['status'])
        # Основная позиция получает ключ сортировки 0, запасная — 1; без фильтра приоритета нет.
        priority = [Case(When(position=position, then=0), default=1)] if position else []
        # *priority раскрывает список ключей; дальше сортируем по рейтингу, дате или нику и затем
        # по ID.
        people = people.order_by(*priority, {'mmr': '-mmr', 'new': '-joined_at'}.get(data.get('sort'), 'nickname'), 'pk')
    # Получаем уникальные непустые названия позиций видимых игроков для выбора в каталоге.
    positions = Person.objects.filter(is_active=True, is_public=True).exclude(position="").values_list("position", flat=True).distinct()
    # У гостя viewer будет None; у вошедшего пытаемся взять связанный профиль.
    viewer = getattr(request.user, 'player_profile', None) if request.user.is_authenticated else None
    # Проверяем, запрошен ли фильтр совместимости по расписанию.
    if request.GET.get('compatible'):
        # Чтобы сравнить время, нужны профиль, дни игры, начало и конец интервала.
        if viewer and viewer.play_days and viewer.play_from and viewer.play_until:
            # Из кандидатов оставляем других игроков, с которыми есть общее игровое окно.
            people = [person for person in people if person.pk != viewer.pk and overlap_reason(viewer, person)]
        # Если данных текущего игрока недостаточно, корректно сравнить расписания нельзя.
        else:
            # Сообщаем посетителю, какие поля заполнить в кабинете.
            messages.info(request, 'Для подбора по времени заполни дни, интервал и часовой пояс в кабинете.')
            # Возвращаем пустую выдачу вместо неподтверждённых совпадений.
            people = []
    # /players?page=2 → в шаблон под ключом people уйдёт вторая страница по 12 игроков.
    # Делим выборку по 12; параметр page выбирает страницу каталога.
    page = Paginator(people, 12).get_page(request.GET.get('page'))
    # Обрабатываем только профили, которые появятся на текущей странице.
    for person in page:
        # Для карточки готовим объяснение совпадения, а для собственного профиля — пустой текст.
        person.compatibility = overlap_reason(viewer, person) if viewer and viewer.pk != person.pk else ''
    # Отправляем шаблону страницу игроков, позиции, введённый запрос и форму фильтров.
    return render(request, "main/people.html", {"people": page, "positions": positions, "position": position, "query": query, 'filters': filters})


# Обрабатываем прямую ссылку на публичный профиль по ID.
def player_detail(request, pk):
    # Один публичный профиль по ключу из /players/<pk>/. awards__achievement проходит
    # по двум связям: от игрока к его наградам, затем к описанию каждого достижения.
    # Ищем только активный публичный профиль и заранее читаем награды с их описаниями.
    person = get_object_or_404(Person.objects.prefetch_related('awards__achievement'), pk=pk, is_active=True, is_public=True)
    # Передаём в шаблон карточки игрока следующий словарь.
    return render(request, 'main/player_detail.html', {
        # Под именем person будет доступен сам найденный профиль.
        'person': person,
        # Показываем открытые объявления этого аккаунта; без аккаунта даём пустой список.
        'listings': PartyListing.objects.filter(account_id=person.account_id, is_active=True, expires_at__gt=timezone.now()) if person.account_id else [],
        # Передаём до пяти уже сыгранных и опубликованных разборов с участием игрока.
        'reports': person.match_reports.filter(is_published=True, played_at__lte=timezone.now())[:5],
        # Передаём его команды из видимых турниров и сразу загружаем данные турниров.
        'teams': person.tournament_teams.filter(tournament__is_published=True).select_related('tournament'),
    # Завершаем render и возвращаем страницу профиля.
    })


# Строим список событий; два необязательных аргумента нужны для повторного показа ошибочной формы.
def events_view(request, registration_form=None, registration_event=None):
    # **identity раскрывает словарь как именованные аргументы filter: для вошедшего
    # ищем по account, для гостя — по visitor_key среди записей без аккаунта.
    # Читаем сессионный ключ, чтобы гость мог увидеть именно свою регистрацию.
    key = request.session.get('community_key')
    # identity хранит условия поиска: аккаунт вошедшего или гостевая запись с подходящим ключом.
    identity = {'account': request.user} if request.user.is_authenticated else {'account__isnull': True, 'visitor_key': key or '__none__'}
    # Запоминаем текущее время как точку отсчёта.
    now = timezone.now()
    # Берём границу на час раньше: уже начавшаяся игра ещё может пересекаться с событием.
    recent = now - timedelta(hours=1)
    # **identity передаёт пары словаря как именованные условия filter; здесь ищем игры капитана.
    games = list(PartyListing.objects.filter(**identity, is_active=True, game_at__gt=recent))
    # Добавляем игры, где посетителя приняли в состав и он уже подтвердил участие.
    games += [r.listing for r in PartyResponse.objects.filter(**identity, is_accepted=True, confirmed_at__isnull=False,
        # По связи listing оставляем активные недавние или будущие игры и читаем их объявления.
        listing__is_active=True, listing__game_at__gt=recent).select_related('listing')]
    # Берём будущие видимые встречи без отмены и подгружаем регистрации для всех встреч.
    events = GuildEvent.objects.filter(is_published=True, is_cancelled=False, starts_at__gte=timezone.now()).prefetch_related("registrations")
    # Для каждой встречи отдельно готовим карточку, очередь и форму.
    for event in events:
        # На основе регистраций вычисляем для карточки свободные места и номер в очереди.
        # Эти атрибуты нужны шаблону events.html, обратно в базу их не записываем.
        # Упорядочиваем записи по времени подачи; при равных датах порядок определяет ID.
        rows = sorted(event.registrations.all(), key=lambda r: (r.created_at, r.pk))
        # Выделяем ожидающих места в том же порядке подачи.
        waiting = [r for r in rows if r.is_waiting]
        # Из числа всех регистраций вычитаем очередь: получаем размер основного состава.
        event.places_taken = len(rows) - len(waiting)
        # Вычитаем занятые места из вместимости; max не даст показать отрицательное число.
        event.places_left = max(0, event.capacity - event.places_taken)
        # next ищет первую запись этого аккаунта или гостевой сессии; если её нет, вернёт None.
        event.my_registration = next((r for r in rows if (r.account_id == request.user.pk if request.user.is_authenticated else key and not r.account_id and r.visitor_key == key)), None)
        # Номер в очереди нужен только посетителю с ожидающей регистрацией.
        if event.my_registration and event.my_registration.is_waiting:
            # В Python первый индекс равен 0; прибавляем 1, чтобы показать посетителю место № 1.
            event.queue_position = waiting.index(event.my_registration) + 1
        # Если конец встречи не задан, при проверке пересечения предполагаем длительность в час.
        end = event.ends_at or event.starts_at + timedelta(hours=1)
        # Два интервала пересекаются, если каждый начинается до конца другого.
        event.conflicts = [g for g in games if g.game_at < end and g.game_at + timedelta(hours=1) > event.starts_at]
        # Сохраняем ошибочную форму у нужной карточки; остальным даём новую с уникальным
        # префиксом.
        event.registration_form = registration_form if event.pk == registration_event else EventRegistrationForm(prefix=f'event-{event.pk}', initial={
            # По возможности подставляем ник из профиля; гостю оставляем поле пустым.
            'nickname': getattr(getattr(request.user, 'player_profile', None), 'display_name', '') if request.user.is_authenticated else '',
        # Закрываем словарь начальных значений и создание формы регистрации.
        })
    # Передаём карточки предстоящих событий в шаблон events.html.
    return render(request, "main/events.html", {"events": events,
        # Добавляем до шести опубликованных прошлых встреч, от новых к старым.
        'past_events': GuildEvent.objects.filter(is_published=True, starts_at__lt=timezone.now()).order_by('-starts_at')[:6]})


# Запись на событие принимаем только методом POST.
@require_POST
# Ограничиваем частоту отправок, чтобы нельзя было бесконечно нажимать «Записаться».
@limit_posts
# Принимаем форму регистрации на конкретное событие из URL.
def event_register(request, pk):
    # Каждая карточка на /events имеет свою форму: prefix отличает её поля от соседних.
    # При ошибке передаём заполненную форму в events_view напрямую, чтобы сохранить ввод.
    # При успехе сохраняем место (или очередь), а redirect('events') заново откроет список.
    # Определяем, прислала ли карточка поле с префиксом event-ID или старое имя без префикса.
    prefix = f'event-{pk}' if f'event-{pk}-nickname' in request.POST else None
    # Читаем отправленные поля формы с выбранным префиксом имён.
    form = EventRegistrationForm(request.POST, prefix=prefix)
    # Объединяем проверку доступных мест и оформление регистрации в транзакцию.
    with transaction.atomic():
        # Блокируем опубликованное событие, чтобы одновременные запросы не забрали одно место.
        event = get_object_or_404(GuildEvent.objects.select_for_update(), pk=pk, is_published=True)
        # Проверяем поля; при ошибке к созданию записи не переходим.
        if not form.is_valid():
            # Вызываем показ списка с этой формой напрямую: введённый ник и ошибки не потеряются.
            return events_view(request, registration_form=form, registration_event=pk)
        # Запрещаем регистрацию на отменённое событие и после времени старта.
        elif event.is_cancelled or event.starts_at <= timezone.now():
            # Готовим сообщение о закрытой регистрации для следующей страницы.
            messages.error(request, 'Регистрация на это событие закрыта.')
        # exists проверяет наличие записи: у вошедшего по аккаунту, у гостя по сессионному ключу.
        elif event.registrations.filter(Q(account=request.user) if request.user.is_authenticated else Q(visitor_key=visitor_key(request))).exists():
            # Если пользователь уже зарегистрирован, сообщаем об этом без новой записи.
            messages.info(request, 'Вы уже записаны на это событие.')
        # Здесь оформляем заявку, если ни одна из предыдущих проверок не остановила запись.
        else:
            # Ищем регистрацию по событию и нику или создаём её; created показывает, новая ли
            # запись.
            _, created = EventRegistration.objects.get_or_create(event=event, nickname=form.cleaned_data['nickname'],
                # defaults подставляется только при создании: сохраняем контакт и ключ сессии.
                defaults={'contact': form.cleaned_data['contact'], 'visitor_key': visitor_key(request),
                          # Для вошедшего указываем аккаунт, для гостя поле остаётся пустым.
                          'account': request.user if request.user.is_authenticated else None,
                          # Если основной состав уже полон, новая регистрация получает флаг
                          # очереди.
                          'is_waiting': event.registered_count >= event.capacity})
            # Получаем запись с этим ником, чтобы прочитать фактический статус.
            registration = event.registrations.get(nickname=form.cleaned_data['nickname'])
            # Выбираем сообщение: посетитель записан, попал в очередь или этот ник был занят.
            messages.success(request, ('Ты в очереди. При освобождении места запись перейдёт в основной состав.' if registration.is_waiting else 'Ты записан! Время встречи и статус записи — в событиях и личном кабинете.') if created else 'Этот ник уже записан.')
    # Возвращаемся к списку событий: браузер запросит актуальную страницу.
    return redirect('events')


# Ограничиваем частоту создания объявлений через POST.
@limit_posts
# На странице пати обрабатываем и публикацию объявления, и просмотр выдачи.
def party_view(request):
    # У /party две формы: GET задаёт фильтры поиска, POST создаёт объявление.
    # После создания переходим на страницу новой пати, подставив listing.pk в её URL.
    # При отправке связываем PartyForm с полями POST; при просмотре создаём пустую форму.
    form = PartyForm(request.POST if request.method == 'POST' else None)
    # Пытаемся создать объявление только из корректно заполненной формы.
    if request.method == 'POST' and form.is_valid():
        # Вычисляем отпечаток полей, чтобы распознать повторный щелчок по кнопке отправки.
        fingerprint = hashlib.sha256(str(sorted(request.POST.items())).encode()).hexdigest()
        # Читаем сведения о последнем объявлении из этой сессии.
        previous = request.session.get('recent_party', {})
        # Сравниваем отпечаток и время: те же поля в течение минуты считаем повтором.
        if previous.get('fingerprint') == fingerprint and timezone.now().timestamp() - previous.get('time', 0) < 60:
            # Перенаправляем на список пати, не создавая вторую запись.
            return redirect('party')
        # Получаем объект объявления в памяти: владельца нужно добавить до сохранения.
        listing = form.save(commit=False)
        # Присваиваем ключ сессии для управления гостевым объявлением.
        listing.visitor_key = visitor_key(request)
        # Проверяем, можно ли дополнительно привязать пати к аккаунту.
        if request.user.is_authenticated:
            # Записываем текущего пользователя в поле владельца объекта.
            listing.account = request.user
        # Сохраняем объявление в базе; теперь у него есть первичный ключ.
        listing.save()
        # Запоминаем отпечаток и время только что опубликованного объявления.
        request.session['recent_party'] = {'fingerprint': fingerprint, 'time': timezone.now().timestamp()}
        # Сохраняем сообщение об успехе для страницы, куда перейдёт браузер.
        messages.success(request, 'Объявление опубликовано. Здесь появятся отклики — выбери игроков для состава.')
        # Строим адрес карточки по имени маршрута party_detail и ID новой пати.
        return redirect('party_detail', pk=listing.pk)
    # Фильтры читаем из GET, отдельно от формы создания объявления.
    filters = PartyFilterForm(request.GET)
    # Используем один момент времени для поиска и проверки альтернативных вариантов.
    now = timezone.now()
    # Получаем профиль для персонального подбора или None, если профиля нет.
    viewer = getattr(request.user, 'player_profile', None)
    # Начальные значения для выдачи и подсказки на случай ошибки фильтров.
    listings, suggestion = [], None
    # Передаём в поиск только данные, которые форма фильтров признала корректными.
    if filters.is_valid():
        # Получаем нормализованные параметры: строки, числа, списки и флаги.
        data = filters.cleaned_data
        # Вызываем подборщик и получаем подходящие объявления.
        listings = search_parties(data, viewer, now)
        # Проверяем случай, когда запрошено совпадение по времени, но расписание не заполнено.
        if data.get('compatible') and not (viewer and viewer.play_days and viewer.play_from and viewer.play_until):
            # Показываем подсказку, где указать доступные дни и часы.
            messages.info(request, 'Для подбора по времени заполни расписание в кабинете.')
        # Если ничего не нашлось, пробуем предложить менее строгие условия.
        if not listings:
            # По очереди пробуем убрать одно условие. Удачный вариант превращаем
            # в ссылку с новыми GET-параметрами; исходные фильтры посетителя не меняем.
            # Перебираем фильтры в порядке, в котором будем предлагать снять ограничение.
            for field in ('mmr', 'role', 'mode', 'goal', 'schedule', 'q', 'microphone', 'evening', 'compatible', 'days', 'after'):
                # Уже пустой или выключенный фильтр не влияет на выдачу.
                if data[field] in (None, '', []) or data[field] is False:
                    # continue сразу переходит к следующему фильтру цикла.
                    continue
                # {**data, field: None} копирует словарь и отключает один фильтр; len считает
                # результаты.
                count = len(search_parties({**data, field: None}, viewer, now))
                # Если снятие фильтра дало хотя бы одну пати, готовим ссылку-подсказку.
                if count:
                    # Создаём изменяемую копию параметров адреса, сохраняя остальные условия
                    # поиска.
                    query = request.GET.copy()
                    # Удаляем из копии только выбранный фильтр; None защищает от ошибки при
                    # отсутствии ключа.
                    query.pop(field, None)
                    # Удаляем номер старой страницы: новую выдачу нужно открыть с начала.
                    query.pop('page', None)
                    # Сохраняем читаемую подпись, число пати и параметры, закодированные для
                    # ссылки.
                    suggestion = {'label': filters.fields[field].label, 'count': count, 'query': query.urlencode()}
                    # Первой полезной подсказки достаточно: выходим из цикла подбора фильтра.
                    break
    # Делим объявления по 12 и выбираем страницу из параметра page.
    listings = Paginator(listings, 12).get_page(request.GET.get('page'))
    # Для каждой видимой карточки готовим дополнительные данные для шаблона.
    for listing in listings:
        # Флаг владельца подскажет шаблону, показывать управление или действие для участника.
        listing.is_owner = owns_listing(request, listing)
        # Вычисляем пояснения о совпадении позиции, рейтинга и расписания.
        listing.compatibility = party_reasons(getattr(request.user, 'player_profile', None) if request.user.is_authenticated else None, listing)
    # Рисуем страницу поиска с выдачей, обеими формами и подсказкой при пустом результате.
    return render(request, 'main/party.html', {'listings': listings, 'form': form, 'filters': filters, 'suggestion': suggestion})


# Ограничиваем частоту отправки откликов.
@limit_posts
# Карточка одной пати: pk определяет объявление, start_form может содержать ошибку времени.
def party_detail(request, pk, start_form=None):
    # GET показывает состав. POST с этой страницы создаёт отклик; форму назначения
    # времени обрабатывает отдельный маршрут party_start в journeys.py.
    # Ищем объявление по ID; за один запрос читаем также аккаунт капитана и его профиль.
    listing = get_object_or_404(PartyListing.objects.select_related('account__player_profile'), pk=pk)
    # Сохраняем результат проверки владельца, он понадобится в нескольких ветках.
    is_owner = owns_listing(request, listing)
    # Для вошедшего ищем отклик по аккаунту, для гостя — по ключу среди записей без аккаунта.
    identity = {'account': request.user} if request.user.is_authenticated else {'visitor_key': request.session.get('community_key', '__none__'), 'account__isnull': True}
    # Закрытое или просроченное объявление скрыто от постороннего без отклика; ** раскрывает
    # словарь условий.
    if not is_owner and not listing.responses.filter(**identity).exists() and (not listing.is_active or listing.expires_at <= timezone.now()):
        # Импортируем класс исключения, которое Django превращает в страницу 404.
        from django.http import Http404
        # raise прерывает обычное выполнение функции: Django ответит «не найдено».
        raise Http404
    # Подключаем форму назначения игры для капитана.
    from .forms import PartyStartForm
    # Подставляем POST только при отправке отклика, а не при ошибке формы времени.
    form = PartyResponseForm(request.POST if request.method == 'POST' and start_form is None else None,
        # При первом открытии берём начальную роль из ?role=, если игрок нажал на конкретный слот.
        initial={'role': request.GET.get('role', '')})
    # Получаем роли для набора; после назначения игры список доступных ролей пуст.
    roles = recruiting_roles(listing) if not listing.game_at else []
    # В списке выбора каждая пара содержит отправляемое значение и видимую подпись роли.
    form.fields['role'].choices = [('', 'Не указана'), *((role, role) for role in roles)]
    # Проверяем метод, поля, наличие свободных ролей, срок и что автор не откликается сам себе.
    if request.method == 'POST' and form.is_valid() and roles and not is_owner and listing.is_active and listing.expires_at > timezone.now():
        # Ищем уже отправленный из этой сессии отклик именно на эту пати.
        existing = listing.responses.filter(visitor_key=visitor_key(request)).first()
        # Если отклик найден, второй из того же браузера создавать не нужно.
        if existing:
            # Вошедший пользователь может привязать свой ранее гостевой отклик.
            if request.user.is_authenticated and existing.account_id is None:
                # Назначаем этому отклику аккаунт пользователя в памяти.
                existing.account = request.user
                # Сохраняем в базе только новое поле владельца.
                existing.save(update_fields=['account'])
            # Поясняем, почему повторная отправка не создала отклик.
            messages.info(request, 'Из этого браузера уже отправлен отклик')
            # Возвращаем браузер на карточку этого же объявления.
            return redirect('party_detail', pk=pk)
        # Определяем, по каким полям искать отклик: аккаунт либо ключ гостя.
        identity = {'account': request.user} if request.user.is_authenticated else {'visitor_key': visitor_key(request)}
        # Копируем проверенные поля формы в словарь и добавляем ключ сессии.
        defaults = {**form.cleaned_data, 'visitor_key': visitor_key(request)}
        # **identity задаёт условия поиска, defaults — значения для новой записи; created сообщает
        # результат.
        response, created = PartyResponse.objects.get_or_create(listing=listing, **identity, defaults=defaults)
        # Уведомление нужно только о новом отклике и только если у капитана есть аккаунт.
        if created and listing.account_id:
            # Обновляем уведомление в отдельной транзакции под блокировкой объявления.
            with transaction.atomic():
                # Читаем строку с блокировкой, чтобы одновременные обновления счётчика шли по
                # очереди.
                PartyListing.objects.select_for_update().get(pk=pk)
                # Подключаем общий помощник для обновления уведомления капитана.
                from .community import refresh_response_notice
                # Обновляем уведомление о новых откликах на данную роль в этой пати.
                refresh_response_notice(listing, response.role, new=True)
        # По флагу created выбираем текст сообщения: новый отклик или уже существующий.
        messages.success(request, 'Отклик отправлен автору.' if created else 'Вы уже откликнулись.')
        # После обработки POST открываем карточку объявления заново через GET.
        return redirect('party_detail', pk=pk)
    # listing.responses — обратная связь: только отклики, указывающие на эту пати.
    # Формируем состав только из принятых участников; подгружаем аккаунты и профили.
    roster = list(listing.responses.filter(is_accepted=True).select_related('account__player_profile'))
    # Увеличиваем просмотры только при открытии страницы не владельцем.
    if request.method == 'GET' and not is_owner:
        # F берёт текущее значение столбца прямо в базе и увеличивает его одним UPDATE.
        # F берёт старое значение поля в базе: прибавляем 1 непосредственно в запросе UPDATE.
        PartyListing.objects.filter(pk=pk).update(detail_views=F('detail_views') + 1)
    # Полный список откликов готовим только для капитана; сортируем по роли и времени.
    responses = list(listing.responses.select_related('account__player_profile').order_by('role', 'created_at')) if is_owner else []
    # Перебираем отклики, которые будут показаны капитану.
    for response in responses:
        # Пробуем получить связанный профиль откликнувшегося игрока.
        profile = getattr(response.account, 'player_profile', None)
        # Добавляем сведения из профиля только если он активен и открыт.
        if profile and profile.is_public and profile.is_active:
            # Передаём разрешённый публичный профиль карточке отклика.
            response.public_profile = profile
            # Сопоставляем расписание капитана и игрока, чтобы объяснить пересечение по времени.
            response.overlap = overlap_reason(getattr(listing.account, 'player_profile', None), profile)
    # Для каждой позиции строим слот: открыт ли набор, капитан ли здесь и кто уже принят.
    slots = [{'role': role, 'recruiting': role in roles, 'captain': role == listing.captain_role, 'member': next((r for r in roster if r.role == role), None)} for role, _ in PartyListing.ROLE_CHOICES[1:]]
    # Передаём шаблону саму пати, форму отклика и флаги доступа к действиям.
    return render(request, 'main/party_detail.html', {'listing': listing, 'form': form, 'can_apply': bool(roles), 'is_owner': is_owner,
        # Добавляем слоты и форму назначения времени; если она с ошибками, используем её повторно.
        'slots': slots, 'start_form': start_form if start_form is not None else PartyStartForm(),
        # Добавляем пояснения, почему эта пати подходит посетителю.
        'compatibility': party_reasons(getattr(request.user, 'player_profile', None) if request.user.is_authenticated else None, listing),
        # Отдельно находим собственный отклик: по аккаунту или гостевому ключу, чтобы показать его
        # статус.
        'my_response': listing.responses.filter(account=request.user).first() if request.user.is_authenticated else listing.responses.filter(visitor_key=request.session.get('community_key', '__none__'), account__isnull=True).first(),
        # Передаём разрешённый список откликов и момент времени для сравнений в шаблоне.
        'responses': responses, 'now': timezone.now(),
        # Под ключом roster передаём принятый состав и завершаем render.
        'roster': roster})


# Закрытие меняет данные: обычный запрос GET не допускается.
@require_POST
# Обрабатываем кнопку закрытия объявления по его ID.
def party_close(request, pk):
    # У чужого объявления возвращаем HTTP 403. У своего снимаем флаг активности:
    # запись остаётся в базе, но больше не показывается в поиске открытых пати.
    # Находим пати; неизвестный ID даст 404, а права проверим дальше.
    listing = get_object_or_404(PartyListing, pk=pk)
    # Если посетитель не владелец, изменение запрещено.
    if not owns_listing(request, listing):
        # return сразу возвращает ответ 403; код снятия объявления ниже не выполняется.
        return HttpResponseForbidden('Закрыть объявление может только автор.')
    # Снимаем флаг активности, не удаляя историю пати из базы.
    listing.is_active = False
    # Записываем только поле is_active, остальные значения не меняем.
    listing.save(update_fields=['is_active'])
    # После закрытия показываем список открытых объявлений.
    return redirect('party')


# Показываем или сохраняем изменения в объявлении владельца.
def party_edit(request, pk):
    # GET подставляет объявление в форму; POST проверяет изменения владельца.
    # Перед сохранением сверяем позицию капитана с составом под блокировкой.
    # Ищем редактируемую пати по ключу из URL.
    listing = get_object_or_404(PartyListing, pk=pk)
    # Сравниваем владельца объявления с текущим посетителем.
    if not owns_listing(request, listing):
        # Для чужой пати сразу отдаём ответ «запрещено» без показа формы.
        return HttpResponseForbidden('Редактировать объявление может только автор')
    # instance подставляет данные этой пати в форму; при POST добавляем введённые поля.
    form = PartyForm(request.POST if request.method == 'POST' else None, instance=listing)
    # Изменяем запись только при корректной отправке формы редактирования.
    if request.method == 'POST' and form.is_valid():
        # Изменение роли и связанный сброс времени должны пройти как одна операция.
        with transaction.atomic():
            # Читаем актуальную версию записи и блокируем её до конца транзакции.
            locked = PartyListing.objects.select_for_update().get(pk=pk)
            # Проверяем, не занята ли предложенная капитану роль уже принятым игроком.
            if locked.responses.filter(is_accepted=True, role=form.cleaned_data['captain_role']).exists():
                # Если роль занята, помещаем сообщение рядом с полем captain_role.
                form.add_error('captain_role', 'Эта позиция уже занята участником')
                # Возвращаем страницу редактирования с ошибкой вместо записи изменений.
                return render(request, 'main/party_edit.html', {'form': form})
            # Берём только действительно изменённые поля, разрешённые этой формой.
            locked_fields = [name for name in form.changed_data if name in form.Meta.fields]
            # Обходим выбранные имена полей по одному.
            for name in locked_fields:
                # setattr записывает значение атрибута по его имени, например locked.nickname.
                setattr(locked, name, form.cleaned_data[name])
            # Если список пуст, делать запрос на сохранение нечего.
            if locked_fields:
                # Записываем только изменённые столбцы в заблокированной строке.
                locked.save(update_fields=locked_fields)
            # При смене капитанской роли у назначенной игры старое время требует пересогласования.
            if 'captain_role' in form.changed_data and locked.game_at:
                # Подключаем помощник для снятия устаревших игровых уведомлений.
                from .community import clear_game_notices
                # Убираем прежние уведомления, относящиеся к игре этой пати.
                clear_game_notices(locked)
                # Сбрасываем дату игры в объекте: None означает «ещё не назначена».
                locked.game_at = None
                # Сохраняем сброс даты в базе.
                locked.save(update_fields=['game_at'])
                # Очищаем старые подтверждения и отметки о напоминаниях у откликов этого
                # объявления.
                locked.responses.update(confirmed_at=None, reminded_for=None)
        # После выхода из транзакции сообщаем об удачном сохранении.
        messages.success(request, 'Объявление обновлено')
        # Возвращаемся на обновлённую карточку по её ключу.
        return redirect('party_detail', pk=pk)
    # При первом открытии или ошибочных полях возвращаем саму форму редактирования.
    return render(request, 'main/party_edit.html', {'form': form})


# Заказ из кабинета доступен только после входа в аккаунт.
@login_required
# Это обработчик страницы заказа: request даёт пользователя, pk приходит из URL.
def account_order(request, pk):
    # Здесь ключ заказа приходит из ссылки в кабинете. Условие account=request.user
    # не даст открыть чужой заказ даже по известному номеру.
    # Ищем заказ одновременно по ID и владельцу, заранее загружаем позиции; иначе получаем 404.
    order = get_object_or_404(MerchOrder.objects.prefetch_related('items'), pk=pk, account=request.user)
    # В шаблоне имя order будет указывать на найденный заказ; браузеру возвращаем HTML.
    return render(request, 'main/order_success.html', {'order': order})

# Обрабатываем список новостей и поиск по их тексту.
def news_view(request):
    # Пример: GET /news?q=турнир&page=2 → main/urls.py выбирает news_view.
    # published() — метод проекта из models.py: исключает черновики и будущие записи.
    # published исключает черновики и будущие публикации, kind оставляет только новости.
    posts = Publication.objects.published().filter(kind=Publication.Kind.NEWS)
    # 'q' — имя параметра в адресе, а query — переменная Python с его значением.
    # В примере query равно 'турнир'. Без q получим ''; strip() убирает пробелы
    # по краям, [:200] оставляет максимум 200 символов поискового текста.
    # q — параметр адреса; strip убирает пробелы по краям, [:200] ограничивает длину запроса.
    query = request.GET.get('q', '').strip()[:200]
    # Если после удаления пробелов остался текст, включаем поиск.
    if query:
        # title__icontains=query: title — поле заголовка, __ отделяет способ поиска,
        # icontains — «содержит этот фрагмент без учёта регистра». Например, «турнир»
        # найдёт заголовок «Новый турнир гильдии». Регистр и сравнение обрабатывает база.
        # Q с большой буквы — класс Django, не параметр 'q'. Три Q через | означают:
        # фрагмент есть в заголовке ИЛИ полном тексте ИЛИ кратком описании.
        # Разделитель __ отделяет поле от icontains; символ | ищет фрагмент в любом из трёх полей.
        posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query) | Q(summary__icontains=query))
    # Paginator делит найденные новости по 9; get_page выбирает страницу из URL.
    # В news.html переменная page_obj содержит эту страницу для вывода списка и ссылок.
    # Разбиваем новости по девять и читаем номер нужной страницы из ?page=.
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    # Имя page_obj связывает полученную страницу со списком и навигацией в news.html.
    return render(request, 'main/news.html', {"page_obj": page})

# Обработчик информационной страницы «Как играем».
def prod_view(request):
    # для этой страницы данные из базы не нужны
    # Возвращаем HTML из prod.html; дополнительные данные из моделей не требуются.
    return render(request, 'main/prod.html')

# Обрабатываем записи дневника, которые хранятся в той же таблице, что и новости.
def blog_view(request):
    # Поиск работает как в news_view; раздел DIARY и шаблон blog.html отличаются.
    # Выбираем только опубликованные записи типа DIARY.
    posts = Publication.objects.published().filter(kind=Publication.Kind.DIARY)
    # Получаем до 200 символов поисковой фразы из URL и удаляем крайние пробелы перед срезом.
    query = request.GET.get('q', '').strip()[:200]
    # Без поискового текста показываем весь доступный дневник постранично.
    if query:
        # Оставляем записи с фразой в заголовке, тексте или кратком описании без учёта регистра.
        posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query) | Q(summary__icontains=query))
    # Выбираем страницу дневника; на каждой помещается до девяти записей.
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    # Передаём текущую страницу в шаблон дневника под именем page_obj.
    return render(request, 'main/blog.html', {"page_obj": page})


# Показываем полный текст одной публикации по номеру из URL.
def publication_detail(request, pk):
    # скрытую запись нельзя открыть даже по прямой ссылке
    # Ищем ID среди доступных публикаций: скрытый материал вернёт 404, даже если ID известен.
    post = get_object_or_404(Publication.objects.published(), pk=pk)
    # В шаблоне подробного просмотра объект публикации будет доступен как post.
    return render(request, "main/publication_detail.html", {"post": post})

# Обработчик информационной страницы о гильдии.
def about_view(request):
    # текст о гильдии лежит в шаблоне
    # Возвращаем посетителю текст и разметку из about.html.
    return render(request, 'main/about.html')

# Обработчик страницы сообществ гильдии.
def communities_view(request):
    # показываем площадки гильдии
    # Возвращаем страницу площадок из communities.html.
    return render(request, 'main/communities.html')

# Поддерживаем прежний адрес главной страницы.
def home_view(request):
    # старый адрес тоже открывает главную
    # Вызываем index с тем же запросом напрямую; адрес в браузере не меняется.
    return index(request)


# При открытии страницы вступления готовим анкету.
def myform(request):
    # показываем анкету а сохраняем в другом обработчике
    # Передаём в myform.html пустую RecruitmentForm; её отправку принимает obr_view.
    return render(request, 'main/myform.html', {'form': RecruitmentForm()})


# Ограничиваем частоту отправки заявок на вступление.
@limit_posts
# Обрабатываем запрос на адрес, указанный в action формы вступления.
def obr_view(request):
    # Путь анкеты: GET /join → myform.html → POST /join/result → проверка и запись
    # FormResult → redirect на /join/saved. При ошибке возвращаем ту же анкету.
    # Ветку сохранения выполняем только при отправке полей методом POST.
    if request.method == 'POST':
        # Вычисляем отпечаток содержимого анкеты для сравнения с предыдущей отправкой.
        fingerprint = hashlib.sha256(str(sorted(request.POST.items())).encode()).hexdigest()
        # Читаем из сессии сведения о предыдущей заявке, если она была.
        previous = request.session.get('recent_recruitment', {})
        # Та же анкета менее чем через минуту считается повторной отправкой.
        if previous.get('fingerprint') == fingerprint and timezone.now().timestamp() - previous.get('time', 0) < 60:
            # Для повтора показываем имеющееся подтверждение, не создавая ещё одну анкету.
            return redirect('recruitment_success')
        # В HTML поле названо user_email, а RecruitmentForm ждёт email. Перекладываем
        # значение в изменяемую копию: сам request.POST по умолчанию неизменяемый.
        # Копируем исходные поля POST, чтобы можно было добавить ключ для формы Django.
        data = request.POST.copy()
        # Имя user_email из HTML перекладываем в email, который ожидает RecruitmentForm.
        data['email'] = data.get('user_email', '')
        # Создаём форму проверки из подготовленного словаря.
        form = RecruitmentForm(data)
        # Если поля не прошли проверку, возвращаемся к анкете.
        if not form.is_valid():
            # Показываем введённые значения и ошибки прямо на странице формы.
            return render(request, 'main/myform.html', {'form': form})
        # Создаём объект заявки в памяти, чтобы успеть указать аккаунт перед записью.
        result = form.save(commit=False)
        # Проверяем, отправил ли анкету вошедший пользователь.
        if request.user.is_authenticated:
            # При наличии аккаунта указываем владельца заявки.
            result.account = request.user
        # Сохраняем анкету в базу и получаем её первичный ключ.
        result.save()
        # Запоминаем ключ для страницы подтверждения после перенаправления.
        request.session['last_recruitment'] = result.pk
        # Сохраняем данные, по которым сможем распознать повтор этой анкеты.
        request.session['recent_recruitment'] = {'fingerprint': fingerprint, 'time': timezone.now().timestamp()}
        # Перенаправляем на подтверждение: браузер выполнит новый GET.
        return redirect('recruitment_success')
    # Если этот адрес открыли без отправки анкеты, показываем страницу её заполнения.
    return redirect('myform')


# Обработчик страницы результата вступительной анкеты.
def recruitment_success(request):
    # После перехода это уже новый запрос: ключ анкеты берём из сессии, не из POST.
    # step и gender — старые имена полей: в этом проекте это MMR и игровая позиция.
    # Находим анкету по ID из этой сессии; при отсутствии заявки отвечаем 404.
    result = get_object_or_404(FormResult, pk=request.session.get('last_recruitment'))
    # Начинаем контекст шаблона результата: передаём имя и рейтинг (старое поле step).
    return render(request, 'main/obr.html', {'myname': result.myname, 'step': result.step,
        # Передаём игровую позицию (gender), почту и Steam ID анкеты.
        'gender': result.gender, 'email': result.email, 'steam_id': result.steam_id,
        # Добавляем часовой пояс и расписание, затем возвращаем заполненный шаблон obr.html.
        'timezone_name': result.timezone_name, 'play_schedule': result.play_schedule})

# Учебная функция с параметром request; явного HTTP-ответа у неё нет.
def test(request):
    # Условное выражение: если 2 > 3, взять 21, иначе 22. Условие ложно, поэтому a равно 22.
    a = 21 if 2>3 else 22




