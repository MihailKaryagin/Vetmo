from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import TournamentTeam
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = [(str(i), day) for i, day in enumerate(('Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'))]


class SignupForm(UserCreationForm):
    email = forms.EmailField(label='Почта для восстановления пароля', required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')
from .models import FormResult, PartyListing, PartyResponse, MerchOrder, Person


class RecruitmentForm(forms.ModelForm):
    gender = forms.ChoiceField(label='Позиция', choices=[('Не указана', 'Выбери позицию'), *PartyListing.ROLE_CHOICES])
    class Meta:
        model = FormResult
        fields = ('myname', 'step', 'gender', 'email', 'steam_id', 'timezone_name', 'play_schedule')

    def clean_step(self):
        value = self.cleaned_data['step']
        if value is not None and (value < 0 or value > 20000 or value != int(value)):
            raise forms.ValidationError('Укажите целый MMR от 0 до 20000.')
        return value


class PartyForm(forms.ModelForm):
    class Meta:
        model = PartyListing
        fields = ('nickname', 'captain_role', 'role', 'mmr_min', 'mmr_max', 'schedule', 'mode', 'goal', 'microphone', 'contact', 'expires_at')
        widgets = {'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}

    def clean(self):
        from django.utils import timezone
        from datetime import timedelta
        data = super().clean()
        expiry = data.get('expires_at')
        if expiry and not timezone.now() < expiry <= timezone.now() + timedelta(days=7):
            self.add_error('expires_at', 'Выберите срок в пределах ближайших семи дней.')
        return data


class EventRegistrationForm(forms.Form):
    nickname = forms.CharField(label='Твой ник', max_length=100)
    contact = forms.CharField(label='Discord / Telegram', max_length=160)


class EmailChangeForm(forms.Form):
    email = forms.EmailField(label='Новая почта', max_length=254)
    password = forms.CharField(label='Текущий пароль', widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class PartyResponseForm(forms.ModelForm):
    class Meta:
        model = PartyResponse
        fields = ('nickname', 'role', 'contact', 'message')


class OrderForm(forms.ModelForm):
    quantity = forms.IntegerField(label='Количество', min_value=1, max_value=99, initial=1)
    size = forms.ChoiceField(label='Размер', required=False)

    class Meta:
        model = MerchOrder
        fields = ('name', 'contact', 'delivery', 'comment')

    def __init__(self, *args, product, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        sizes = [size.strip() for size in product.sizes.split(',') if size.strip()]
        variants = list(product.variants.order_by('size'))
        if variants:
            sizes = [variant.size for variant in variants if variant.stock > 0]
        self.fields['size'].choices = [(size, size) for size in sizes]
        self.fields['size'].required = bool(sizes)
        if not sizes:
            self.fields['size'].widget = forms.HiddenInput()
        if variants and not sizes:
            self.fields['quantity'].help_text = 'Все размеры закончились'


class ProfileForm(forms.ModelForm):
    position = forms.ChoiceField(label='Основная позиция', required=False, choices=[('', 'Не указана'), *PartyListing.ROLE_CHOICES[1:]])
    backup_position = forms.ChoiceField(label='Запасная позиция', required=False, choices=[('', 'Не указана'), *PartyListing.ROLE_CHOICES[1:]])
    play_days = forms.MultipleChoiceField(label='Дни игры', choices=WEEKDAYS, required=False, widget=forms.CheckboxSelectMultiple, help_text='Укажи дни и время, чтобы видеть общее окно с капитаном.')
    class Meta:
        model = Person
        fields = ('name', 'nickname', 'position', 'mmr', 'steam_url', 'avatar_url', 'timezone_name', 'play_schedule', 'play_days', 'play_from', 'play_until', 'favorite_heroes', 'bio', 'status', 'goal', 'is_public')
        fields += ('backup_position', 'looking_until', 'remind_game')
        help_texts = {'play_days': 'Укажи дни и время, чтобы найти пати с общим игровым окном.'}
        widgets = {'looking_until': forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'), 'bio': forms.Textarea(attrs={'rows': 4}), 'play_from': forms.TimeInput(attrs={'type': 'time'}), 'play_until': forms.TimeInput(attrs={'type': 'time'})}

    def clean_timezone_name(self):
        value = self.cleaned_data['timezone_name'].strip()
        if value:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError):
                raise forms.ValidationError('Укажи часовой пояс, например Europe/Moscow или Asia/Yekaterinburg.')
        return value

    def clean(self):
        data = super().clean()
        if data.get('backup_position') and data['backup_position'] == data.get('position'):
            self.add_error('backup_position', 'Запасная позиция должна отличаться от основной.')
        if data.get('status') != 'looking':
            data['looking_until'] = None
        elif data.get('looking_until'):
            from django.utils import timezone
            if data['looking_until'] < timezone.localdate(timezone=ZoneInfo(data.get('timezone_name') or 'Europe/Moscow')):
                self.add_error('looking_until', 'Выбери сегодня или более позднюю дату.')
        if any((data.get('play_days'), data.get('play_from'), data.get('play_until'))):
            if not all((data.get('play_days'), data.get('play_from'), data.get('play_until'), data.get('timezone_name'))):
                self.add_error(None, 'Для подбора по расписанию укажи дни, начало, конец и часовой пояс. Интервал может переходить через полночь.')
            elif data['play_from'] == data['play_until']:
                self.add_error('play_until', 'Начало и конец не должны совпадать.')
        return data

    def clean_mmr(self):
        value = self.cleaned_data['mmr']
        if value is not None and value > 20000:
            raise forms.ValidationError('Укажите MMR от 0 до 20000')
        return value


class PartyStartForm(forms.Form):
    game_at = forms.DateTimeField(label='Начало игры (в твоём часовом поясе)', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))

    def clean_game_at(self):
        from django.utils import timezone
        from datetime import timedelta
        value = self.cleaned_data['game_at']
        if not timezone.now() < value <= timezone.now() + timedelta(days=14):
            raise forms.ValidationError('Выбери время в ближайшие 14 дней.')
        return value

class PartyFilterForm(forms.Form):
    days = forms.MultipleChoiceField(label='Дни доступности капитана (в твоём часовом поясе)', choices=WEEKDAYS, required=False)
    after = forms.TimeField(label='Свободное окно после', widget=forms.TimeInput(attrs={'type': 'time'}), required=False)
    evening = forms.BooleanField(label='Свободны сегодня вечером', required=False)
    evening_from = forms.TimeField(label='Начало окна (по умолчанию 18:00)', required=False, widget=forms.TimeInput(attrs={'type':'time'}))
    evening_to = forms.TimeField(label='Конец окна (по умолчанию 23:00)', required=False, widget=forms.TimeInput(attrs={'type':'time'}))
    compatible = forms.BooleanField(label='Есть общее время со мной', required=False)
    q = forms.CharField(label='Ник', required=False, max_length=100)
    role = forms.ChoiceField(label='Позиция', required=False, choices=[('', 'Все позиции'), *PartyListing.ROLE_CHOICES])
    mmr = forms.IntegerField(label='Мой MMR', required=False, min_value=0, max_value=20000)
    schedule = forms.CharField(label='Время игры', required=False, max_length=160)
    mode = forms.ChoiceField(label='Режим', required=False, choices=[('', 'Все режимы'), ('Рейтинг', 'Рейтинговая'), ('Обычная', 'Обычная')])
    goal = forms.ChoiceField(label='Цель', required=False, choices=[('', 'Все цели'), *PartyListing._meta.get_field('goal').choices])
    microphone = forms.BooleanField(label='С микрофоном', required=False)


class PlayerFilterForm(forms.Form):
    compatible = forms.BooleanField(label='Есть общее время со мной', required=False)
    q = forms.CharField(label='Ник', required=False, max_length=100)
    position = forms.ChoiceField(label='Позиция', required=False, choices=[('', 'Все позиции'), *PartyListing.ROLE_CHOICES[1:]])
    goal = forms.ChoiceField(label='Цель', required=False, choices=[('', 'Все цели'), *Person._meta.get_field('goal').choices])
    status = forms.ChoiceField(label='Статус', required=False, choices=[('', 'Любой статус'), *Person._meta.get_field('status').choices])
    mmr_min = forms.IntegerField(label='MMR от', required=False, min_value=0)
    mmr_max = forms.IntegerField(label='MMR до', required=False, min_value=0)
    schedule = forms.CharField(label='Время игры', required=False, max_length=160)
    sort = forms.ChoiceField(label='Сортировка', required=False, choices=(('name', 'По нику'), ('mmr', 'По MMR'), ('new', 'Новые участники')))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['aria-label'] = field.label
            field.widget.attrs['placeholder'] = field.label

    def clean(self):
        data = super().clean()
        if data.get('mmr_min') is not None and data.get('mmr_max') is not None and data['mmr_min'] > data['mmr_max']:
            self.add_error('mmr_max', 'Верхняя граница должна быть не ниже нижней.')
        return data


class TournamentTeamForm(forms.ModelForm):
    class Meta:
        model = TournamentTeam
        fields = ('name', 'roster')

    def clean_roster(self):
        value = self.cleaned_data['roster']
        if len([line for line in value.splitlines() if line.strip()]) != 5:
            raise forms.ValidationError('Укажите пять игроков каждый на отдельной строке')
        return value
