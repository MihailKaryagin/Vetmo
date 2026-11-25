from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
import uuid
from datetime import timedelta


def party_expiry():
    return timezone.now() + timedelta(days=1)


# общая выборка новостей и дневника
class PublicationQuerySet(models.QuerySet):
    def published(self):
        # показываем запись когда наступила дата публикации
        return self.filter(is_published=True, published_at__lte=timezone.now())


class SupportConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField('Закрыт', default=False)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Диалог поддержки'
        verbose_name_plural = 'Поддержка — диалоги'

    def __str__(self):
        return f'Чат {str(self.pk)[:8]}'


class SupportMessage(models.Model):
    COLORS = (('', 'Обычный'), ('#8ec5ff', 'Голубой'), ('#b9e68c', 'Лайм'),
              ('#ffc980', 'Персик'), ('#e4b1ff', 'Лиловый'), ('#ff9bb5', 'Розовый'))
    conversation = models.ForeignKey(SupportConversation, on_delete=models.CASCADE, related_name='messages')
    text = models.TextField()
    color = models.CharField(max_length=7, blank=True, default='', choices=COLORS)
    from_operator = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_update_id = models.BigIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ('pk',)


class SupportBotState(models.Model):
    # храним последнее обновление чтобы не получать сообщения повторно
    offset = models.BigIntegerField(default=0)


class Publication(models.Model):
    # в базе короткие значения а на сайте русские подписи
    class Kind(models.TextChoices):
        DIARY = "diary", "Дневник"
        NEWS = "news", "Новость"

    title = models.CharField("Заголовок", max_length=200)
    kind = models.CharField("Раздел", max_length=10, choices=Kind.choices, default=Kind.DIARY)
    summary = models.TextField("Краткое описание", max_length=500, blank=True)
    body = models.TextField("Текст публикации", help_text="Пишите обычный текст. Разделяйте абзацы пустой строкой — на сайте они сохранятся.")
    is_published = models.BooleanField("Опубликовано", default=False)
    published_at = models.DateTimeField("Дата публикации", default=timezone.now, help_text="Будущая дата отложит появление записи на сайте.")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    # добавляем выборку опубликованных записей
    objects = PublicationQuerySet.as_manager()

    class Meta:
        verbose_name = "Публикация"
        verbose_name_plural = "Публикации"
        # новые записи выводим первыми
        ordering = ("-published_at", "-pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        # ссылку собираем по имени маршрута
        return reverse("publication_detail", args=[self.pk])


class FormResult(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    # старые названия полей оставили чтобы сохранить данные
    # тут step это ммр а gender это позиция
    myname = models.CharField("Имя", max_length=100)
    step = models.DecimalField("Шаг", max_digits=10, decimal_places=2, blank=True, null=True)
    gender = models.CharField("Пол", max_length=30)
    email = models.EmailField("Электронная почта", blank=True)
    birthdate = models.DateField("Дата рождения", blank=True, null=True)
    STATUS_CHOICES = (
        ("new", "Новая"),
        ("review", "На рассмотрении"),
        ("accepted", "Принята"),
        ("rejected", "Отклонена"),
    )
    status = models.CharField("Статус заявки", max_length=12, choices=STATUS_CHOICES, default="new")
    admin_comment = models.TextField("Комментарий администратора", blank=True)
    steam_id = models.CharField("Steam ID / ссылка", max_length=255, blank=True)
    timezone_name = models.CharField("Часовой пояс", max_length=80, blank=True)
    play_schedule = models.CharField("Когда играет", max_length=160, blank=True)

    class Meta:
        verbose_name = "Результат формы"
        verbose_name_plural = "Результаты формы"

    def __str__(self):
        return self.myname


class User(models.Model):
    # это контакт а для входа используется встроенный пользователь django
    name = models.CharField("Имя", max_length=100)
    email = models.EmailField("Электронная почта")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.name


class Person(models.Model):
    backup_position = models.CharField('Запасная позиция', max_length=40, blank=True)
    looking_until = models.DateField('Ищу пати до (включительно)', null=True, blank=True)
    remind_game = models.BooleanField('Напомнить за час до игры', default=False)
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='player_profile', verbose_name='Аккаунт')
    # игроки которые отображаются на сайте
    name = models.CharField("Имя", max_length=20)
    age = models.IntegerField("Возраст", null=True, blank=True)
    nickname = models.CharField("Игровой ник", max_length=80, blank=True)
    position = models.CharField("Основная позиция", max_length=40, blank=True)
    mmr = models.PositiveIntegerField("MMR", null=True, blank=True)
    steam_url = models.URLField("Steam", blank=True)
    avatar_url = models.URLField("Ссылка на аватар", blank=True)
    timezone_name = models.CharField("Часовой пояс", max_length=80, blank=True)
    play_schedule = models.CharField("Когда играет", max_length=160, blank=True)
    is_active = models.BooleanField("Показывать на сайте", default=True)
    is_public = models.BooleanField('Открытый профиль', default=True)
    favorite_heroes = models.CharField("Любимые герои", max_length=255, blank=True)
    bio = models.TextField("О себе", blank=True)
    status = models.CharField("Статус", max_length=20, choices=(('looking', 'Ищет пати'), ('busy', 'Занят'), ('training', 'Тренировка')), default='looking')
    goal = models.CharField('Цель игры', max_length=20, choices=(('rating', 'Поднять рейтинг'), ('fun', 'Обычные игры'), ('team', 'Постоянный состав')), default='team')
    play_days = models.JSONField('Дни игры (0 — понедельник)', default=list, blank=True)
    play_from = models.TimeField('Играю с', null=True, blank=True)
    play_until = models.TimeField('Играю до', null=True, blank=True)
    joined_at = models.DateField("В гильдии с", default=timezone.localdate)

    @property
    def display_name(self):
        return self.nickname or self.name

    @property
    def hero_portraits(self):
        from .heroes import hero_portraits
        return hero_portraits(self.favorite_heroes)

    class Meta:
        verbose_name = "Человек"
        verbose_name_plural = "Люди"
        indexes = [models.Index(fields=['position', 'goal', 'is_active', 'is_public', '-mmr', 'id'],
                                name='player_role_goal_mmr')]

    def __str__(self):
        return self.name


class Category(models.Model):
    # категории нужны для каталога и фильтра по сезону
    name = models.CharField("Название", max_length=255)
    category = models.CharField("Категория", max_length=255)

    class Meta:
        db_table = "category"
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Product(models.Model):
    # ссылки на фотографии меняем в админке
    name = models.CharField("Название", max_length=255)
    image_url = models.URLField("Ссылка на фото", max_length=1000, blank=True)
    image_source = models.URLField("Источник фотографии", max_length=1000, blank=True)
    sale = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    material = models.CharField("Материал", max_length=255)
    data_prod = models.DateField("Дата производства")
    counter = models.IntegerField("Количество")
    nalichie = models.BooleanField("В наличии", default=True)
    description = models.TextField("Описание", blank=True)
    sizes = models.CharField("Размеры", max_length=255, blank=True, help_text="Например: S, M, L, XL")
    # при удалении категории удаляются ее товары
    cat_id = models.ForeignKey(
        Category,
        verbose_name="Категория",
        on_delete=models.CASCADE,
        related_name="products",
    )

    class Meta:
        db_table = "products"
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    @property
    def can_order(self):
        if not self.nalichie or self.counter <= 0:
            return False
        variants = list(self.variants.all())
        return not variants or any(v.stock for v in variants)

    def __str__(self):
        return self.name


class GuildEvent(models.Model):
    title = models.CharField("Название", max_length=160)
    description = models.TextField("Описание")
    starts_at = models.DateTimeField("Начало")
    ends_at = models.DateTimeField("Окончание", null=True, blank=True)
    capacity = models.PositiveIntegerField("Мест", default=10, validators=[MinValueValidator(1)])
    is_published = models.BooleanField("Опубликовано", default=True)
    format = models.CharField("Формат", max_length=100, default="Командная игра")
    is_cancelled = models.BooleanField("Отменено", default=False)

    class Meta:
        ordering = ("starts_at",)
        verbose_name = "Событие"
        verbose_name_plural = "События"

    @property
    def registered_count(self):
        return self.registrations.filter(is_waiting=False).count()

    @property
    def free_places(self):
        return max(0, self.capacity - self.registered_count)

    def __str__(self):
        return self.title

    def clean(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'Окончание должно быть позже начала.'})


class EventRegistration(models.Model):
    is_waiting = models.BooleanField('В очереди', default=False)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey(GuildEvent, on_delete=models.CASCADE, related_name="registrations")
    nickname = models.CharField("Ник", max_length=100)
    contact = models.CharField("Контакт", max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    visitor_key = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        unique_together = ("event", "nickname")
        verbose_name = "Регистрация на событие"
        verbose_name_plural = "Регистрации на события"


class PartyListing(models.Model):
    detail_views = models.PositiveIntegerField(default=0, editable=False)
    game_at = models.DateTimeField('Подтверждённый старт', null=True, blank=True)
    captain_role = models.CharField('Позиция капитана', max_length=30, default='Керри / 1', choices=(('Керри / 1', 'Керри / 1'), ('Мид / 2', 'Мид / 2'), ('Оффлейн / 3', 'Оффлейн / 3'), ('Поддержка / 4', 'Поддержка / 4'), ('Полная поддержка / 5', 'Полная поддержка / 5')))
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ROLE_CHOICES = (
        ("Любая", "Любая позиция"),
        ("Керри / 1", "Керри / 1"),
        ("Мид / 2", "Мид / 2"),
        ("Оффлейн / 3", "Оффлейн / 3"),
        ("Поддержка / 4", "Поддержка / 4"),
        ("Полная поддержка / 5", "Полная поддержка / 5"),
    )
    nickname = models.CharField("Ник", max_length=100)
    role = models.CharField("Ищу позицию", max_length=30, choices=ROLE_CHOICES, default="Любая")
    mmr_min = models.PositiveIntegerField("MMR от", null=True, blank=True)
    mmr_max = models.PositiveIntegerField("MMR до", null=True, blank=True)
    schedule = models.CharField("Когда играю", max_length=160)
    mode = models.CharField("Режим", max_length=80, default="Рейтинг")
    contact = models.CharField("Контакт", max_length=160, blank=True)
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("Актуально до", default=party_expiry)
    goal = models.CharField("Цель", max_length=30, choices=(('rating', 'Поднять рейтинг'), ('fun', 'Поиграть в удовольствие'), ('learn', 'Обучение')), default='fun')
    microphone = models.BooleanField("С микрофоном", default=True)
    visitor_key = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Объявление поиска пати"
        verbose_name_plural = "Объявления поиска пати"

    def __str__(self):
        return f"{self.nickname} — {self.role}"

    def clean(self):
        if self.mmr_min is not None and self.mmr_max is not None and self.mmr_min > self.mmr_max:
            raise ValidationError({'mmr_max': 'Верхняя граница MMR должна быть не ниже нижней.'})


class PartyResponse(models.Model):
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    removed_at = models.DateTimeField(null=True, blank=True, editable=False)
    reminded_for = models.DateTimeField(null=True, blank=True, editable=False)
    confirmed_at = models.DateTimeField('Участие подтверждено', null=True, blank=True)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField('Позиция', max_length=30, blank=True, choices=PartyListing.ROLE_CHOICES[1:])
    is_accepted = models.BooleanField('Принят в состав', default=False)
    listing = models.ForeignKey(PartyListing, on_delete=models.CASCADE, related_name='responses')
    nickname = models.CharField("Ник", max_length=100)
    contact = models.CharField("Контакт", max_length=160)
    message = models.CharField("Сообщение", max_length=500, blank=True)
    visitor_key = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Отклик на пати'
        verbose_name_plural = 'Отклики на пати'
        constraints = [models.UniqueConstraint(fields=['listing', 'visitor_key'], name='unique_party_response_visitor')]


class MerchOrder(models.Model):
    STATUS_CHOICES = (('new', 'Новый'), ('confirmed', 'Подтверждён'), ('shipped', 'Отправлен'), ('cancelled', 'Отменён'))
    stock_returned = models.BooleanField('Остатки возвращены', default=False, editable=False)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Имя", max_length=100)
    contact = models.CharField("Контакт", max_length=160)
    delivery = models.CharField("Город / способ доставки", max_length=255)
    comment = models.TextField("Комментарий", blank=True, max_length=1000)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заказ мерча'
        verbose_name_plural = 'Заказы мерча'
        ordering = ('-created_at',)

    @property
    def total(self):
        return sum(item.price * item.quantity for item in self.items.all())

    def __str__(self):
        return f'Заказ {str(self.pk)[:8]} — {self.name}'

    def save(self, **kwargs):
        if not self._state.adding:
            return super().save(**kwargs)
        with transaction.atomic(using=kwargs.get('using')):
            super().save(**kwargs)
            self.history.create(status=self.status, changed_at=self.created_at)


class OrderStatusEvent(models.Model):
    order = models.ForeignKey(MerchOrder, on_delete=models.CASCADE, related_name='history')
    status = models.CharField(max_length=20, choices=MerchOrder.STATUS_CHOICES)
    changed_at = models.DateTimeField(default=timezone.now, null=True)

    class Meta:
        ordering = ('pk',)

    @property
    def explanation(self):
        return {
            'new': 'Оператор проверит заказ и свяжется с тобой.',
            'confirmed': 'Оператор готовит товары и передаст их в доставку.',
            'shipped': 'Перевозчик доставляет заказ. Дождись уведомления о получении.',
            'cancelled': 'Заказ отменён. Отправки не будет; от тебя ничего не требуется.',
        }[self.status]


class MerchOrderItem(models.Model):
    order = models.ForeignKey(MerchOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    name = models.CharField("Товар", max_length=255)
    size = models.CharField("Размер", max_length=40, blank=True)
    quantity = models.PositiveIntegerField("Количество", validators=[MinValueValidator(1), MaxValueValidator(99)])
    price = models.DecimalField("Цена на момент заказа", max_digits=10, decimal_places=2)


class ProductVariant(models.Model):
    width_cm = models.PositiveSmallIntegerField('Ширина изделия, см', null=True, blank=True)
    length_cm = models.PositiveSmallIntegerField('Длина изделия, см', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField('Размер', max_length=40)
    stock = models.PositiveIntegerField('Остаток', default=0)

    class Meta:
        verbose_name = 'Размер товара'
        verbose_name_plural = 'Размеры и остатки'
        constraints = [models.UniqueConstraint(fields=['product', 'size'], name='unique_product_size')]

    def __str__(self):
        return f'{self.size} — {self.stock}'


class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    image_url = models.URLField('Ссылка на фото', max_length=1000)
    caption = models.CharField('Описание фото', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Фотография товара'
        verbose_name_plural = 'Фотографии товара'


class Notification(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    text = models.CharField('Сообщение', max_length=255)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')


class Favorite(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True)
    listing = models.ForeignKey(PartyListing, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(person__isnull=False, listing__isnull=True, product__isnull=True) | models.Q(person__isnull=True, listing__isnull=False, product__isnull=True) | models.Q(person__isnull=True, listing__isnull=True, product__isnull=False)), name='favorite_one_target'),
            *[models.UniqueConstraint(fields=['account', field], name=f'unique_favorite_{field}') for field in ('person', 'listing', 'product')],
        ]


class Achievement(models.Model):
    title = models.CharField('Название', max_length=120, unique=True)
    description = models.TextField('Описание')

    def __str__(self):
        return self.title


class PlayerAchievement(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='awards')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    awarded_at = models.DateField('Дата выдачи', default=timezone.localdate)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['person', 'achievement'], name='unique_player_achievement')]


class MatchReport(models.Model):
    topic = models.CharField('Тема разбора', max_length=80, blank=True)
    match_id = models.PositiveBigIntegerField('ID матча Dota 2', null=True, blank=True, unique=True)
    duration = models.PositiveIntegerField('Продолжительность, секунд', null=True, blank=True)
    key_moment = models.TextField('Ключевой момент', blank=True)
    went_well = models.TextField('Что получилось', blank=True)
    next_steps = models.TextField('На следующую игру', blank=True)
    match_stats = models.JSONField('Статистика OpenDota', default=dict, blank=True)
    stats_updated_at = models.DateTimeField('Статистика обновлена', null=True, blank=True)
    title = models.CharField('Название', max_length=160)
    played_at = models.DateTimeField('Дата игры', default=timezone.now)
    won = models.BooleanField('Победа', default=True)
    score = models.CharField('Счёт', max_length=30)
    roster = models.TextField('Состав и герои')
    analysis = models.TextField('Разбор капитана')
    is_published = models.BooleanField('Опубликовано', default=True)
    players = models.ManyToManyField(Person, blank=True, related_name='match_reports', verbose_name='Игроки')
    tournament_match = models.ForeignKey('TournamentMatch', null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='reports', verbose_name='Матч турнира')

    @property
    def roster_portraits(self):
        from .heroes import hero_portraits
        result = []
        for line in self.roster.splitlines():
            nickname, separator, hero = line.partition(' — ')
            result.append({'nickname': nickname, 'heroes': hero_portraits(hero) if separator else []})
        return result

    class Meta:
        ordering = ('-played_at',)

    def __str__(self):
        return self.title


class Tournament(models.Model):
    title = models.CharField('Название', max_length=160, unique=True)
    description = models.TextField('Описание')
    starts_at = models.DateTimeField('Начало')
    registration_ends_at = models.DateTimeField('Конец регистрации')
    is_published = models.BooleanField('Опубликовано', default=True)

    def __str__(self):
        return self.title

    @property
    def winner(self):
        matches = list(self.matches.all())
        if not matches or any(not match.is_finished for match in matches):
            return None
        final_round = max(match.round for match in matches)
        finals = [match for match in matches if match.round == final_round]
        if len(finals) != 1 or finals[0].score_a == finals[0].score_b:
            return None
        final = finals[0]
        return final.team_a if final.score_a > final.score_b else final.team_b

    @property
    def status_label(self):
        if self.winner:
            return 'Завершён'
        if self.registration_ends_at > timezone.now():
            return 'Регистрация открыта'
        return 'Скоро старт' if self.starts_at > timezone.now() else 'Идёт турнир'


class TournamentTeam(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='teams')
    captain = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField('Команда', max_length=100)
    roster = models.TextField('Пять игроков и позиции', max_length=1000)
    players = models.ManyToManyField(Person, blank=True, related_name='tournament_teams', verbose_name='Профили игроков')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tournament', 'captain'], name='unique_tournament_captain'), models.UniqueConstraint(fields=['tournament', 'name'], name='unique_tournament_team')]

    def __str__(self):
        return self.name


class TournamentMatch(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    round = models.PositiveIntegerField('Раунд', default=1)
    team_a = models.ForeignKey(TournamentTeam, on_delete=models.CASCADE, related_name='+')
    team_b = models.ForeignKey(TournamentTeam, on_delete=models.CASCADE, related_name='+')
    score_a = models.PositiveIntegerField('Счёт первой команды', default=0)
    score_b = models.PositiveIntegerField('Счёт второй команды', default=0)
    is_finished = models.BooleanField('Завершён', default=False)
    starts_at = models.DateTimeField('Время матча', null=True, blank=True)

    class Meta:
        ordering = ('round', 'pk')

    def clean(self):
        if self.team_a_id and self.team_b_id:
            if self.team_a_id == self.team_b_id or self.team_a.tournament_id != self.tournament_id or self.team_b.tournament_id != self.tournament_id:
                raise ValidationError('Выберите две разные команды этого турнира')
        if self.is_finished and self.score_a == self.score_b:
            raise ValidationError('У завершенного матча должен быть победитель')


class Poll(models.Model):
    scenario = models.TextField('Игровая ситуация', blank=True)
    explanation = models.TextField('Объяснение после ответа', blank=True)
    title = models.CharField('Вопрос', max_length=200, unique=True)
    closes_at = models.DateTimeField('Голосование до')
    is_published = models.BooleanField('Опубликовано', default=True)

    def __str__(self):
        return self.title


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField('Ответ', max_length=160)

    def __str__(self):
        return self.text


class MatchMoment(models.Model):
    report = models.ForeignKey(MatchReport, on_delete=models.CASCADE, related_name='moments')
    seconds = models.PositiveIntegerField('Секунда матча')
    description = models.CharField('Решение и причина', max_length=500)
    clip_url = models.URLField('Ссылка на эпизод с таймкодом', blank=True)

    @property
    def timestamp(self):
        minutes, seconds = divmod(self.seconds, 60)
        return f'{minutes}:{seconds:02d}'

    class Meta:
        ordering = ('seconds', 'pk')


class SavedPartySearch(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='party_searches')
    name = models.CharField(max_length=80)
    query = models.CharField(max_length=2000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['account', 'name'], name='unique_named_party_search')]


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    choice = models.ForeignKey(PollChoice, on_delete=models.CASCADE, related_name='votes')
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['poll', 'account'], name='unique_poll_vote')]


class FormThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    window_start = models.DateTimeField(default=timezone.now)
    count = models.PositiveIntegerField(default=0)
