from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Subquery
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.shortcuts import get_object_or_404
from .models import SupportConversation, SupportMessage
from .models import ProductVariant, ProductPhoto, Notification
from .models import Achievement, PlayerAchievement, MatchReport, Tournament, TournamentTeam, TournamentMatch, Poll, PollChoice, PollVote
from .services import change_order_status
from .models import FormResult, User, Person, Category, Product, Publication, GuildEvent, EventRegistration, PartyListing, PartyResponse, MerchOrder, MerchOrderItem


# заголовки админки
admin.site.site_header = "vetmo — панель управления"
admin.site.site_title = "vetmo"
admin.site.index_title = "Управление vetmo"


class SupportReplyForm(forms.Form):
    text = forms.CharField(label='Ответ посетителю', max_length=2000, strip=True,
                           widget=forms.Textarea(attrs={'rows': 3, 'maxlength': 2000}))
    color = forms.ChoiceField(label='Цвет текста', choices=SupportMessage.COLORS, required=False)


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'reply_status', 'last_text', 'last_activity', 'created_at')
    actions = None
    change_list_template = 'admin/main/supportconversation/change_list.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        latest = SupportMessage.objects.filter(conversation_id=OuterRef('pk')).order_by('-pk')
        return super().get_queryset(request).annotate(
            last_id=Subquery(latest.values('pk')[:1]),
            last_from_operator=Subquery(latest.values('from_operator')[:1]),
            last_body=Subquery(latest.values('text')[:1]),
            last_time=Subquery(latest.values('created_at')[:1]),
        ).order_by('-last_id', '-created_at')

    @admin.display(description='Статус', ordering='last_from_operator')
    def reply_status(self, obj):
        if obj.is_closed:
            return 'Закрыт'
        if obj.last_id is None:
            return 'Нет сообщений'
        return 'Ответ отправлен' if obj.last_from_operator else '● Ждёт ответа'

    @admin.display(description='Последнее сообщение')
    def last_text(self, obj):
        return (obj.last_body or '')[:100]

    @admin.display(description='Последняя активность', ordering='last_time')
    def last_activity(self, obj):
        return obj.last_time

    def get_urls(self):
        return [path('<uuid:object_id>/messages/', self.admin_site.admin_view(self.chat_messages),
                     name='main_supportconversation_messages')] + super().get_urls()

    def chat_messages(self, request, object_id):
        if request.method != 'GET':
            return JsonResponse({'error': 'Метод не поддерживается.'}, status=405)
        obj = get_object_or_404(SupportConversation, pk=object_id)
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        try:
            after = int(request.GET.get('after', '0'))
            if not 0 <= after <= 9223372036854775807:
                raise ValueError
        except ValueError:
            return JsonResponse({'error': 'Некорректный номер сообщения.'}, status=400)
        if request.GET.get('revision', str(obj.revision)) != str(obj.revision):
            after = 0
        rows = obj.messages.filter(pk__gt=after)[:100]
        return JsonResponse({'revision': obj.revision, 'is_closed': obj.is_closed, 'messages': [
            {'id': row.pk, 'text': row.text, 'from_operator': row.from_operator,
             'created_at': row.created_at.isoformat(), 'color': row.color} for row in rows
        ]})

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        can_reply = self.has_change_permission(request, obj)
        form = SupportReplyForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST':
            if not can_reply:
                raise PermissionDenied
            action = request.POST.get('action', 'reply')
            with transaction.atomic():
                obj = SupportConversation.objects.select_for_update().get(pk=obj.pk)
                if action == 'clear':
                    obj.messages.all().delete()
                    obj.revision += 1
                    obj.save(update_fields=['revision'])
                elif action in ('close', 'reopen'):
                    obj.is_closed = action == 'close'
                    obj.save(update_fields=['is_closed'])
                elif action == 'reply' and form.is_valid():
                    if obj.is_closed:
                        form.add_error('text', 'Откройте диалог перед отправкой ответа.')
                    else:
                        obj.messages.create(text=form.cleaned_data['text'], color=form.cleaned_data['color'], from_operator=True)
                elif action != 'reply':
                    raise PermissionDenied
            if not form.errors or action in ('clear', 'close', 'reopen'):
                return HttpResponseRedirect(reverse('admin:main_supportconversation_change', args=[obj.pk]))
        context = {
            **self.admin_site.each_context(request),
            'title': str(obj), 'opts': self.model._meta, 'original': obj,
            'form': form, 'can_reply': can_reply,
            'messages_url': reverse('admin:main_supportconversation_messages', args=[obj.pk]),
            **(extra_context or {}),
        }
        return TemplateResponse(request, 'admin/main/supportconversation/chat.html', context)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    def get_urls(self):
        return [path('weekly-draft/', self.admin_site.admin_view(self.weekly_draft),
                     name='main_publication_weekly_draft')] + super().get_urls()

    def weekly_draft(self, request):
        from django.core.management import call_command
        from django.http import HttpResponseNotAllowed
        from django.utils import timezone
        from io import StringIO
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not self.has_add_permission(request) or not self.has_change_permission(request):
            raise PermissionDenied
        call_command('weekly_draft', stdout=StringIO())
        draft = Publication.objects.get(kind='news', title=f'Итоги недели · {timezone.localdate():%G-W%V}')
        return HttpResponseRedirect(reverse('admin:main_publication_change', args=[draft.pk]))

    # колонки фильтры и поля редактора
    list_display = ("title", "kind", "is_published", "published_at", "updated_at")
    list_filter = ("kind", "is_published", "published_at")
    search_fields = ("title", "summary", "body")
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25
    fieldsets = (
        ("Запись", {"fields": ("title", "kind", "summary", "body")}),
        ("Публикация", {"fields": ("is_published", "published_at")}),
        ("История изменений", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    class Media:
        # дополнительные стили для редактора
        css = {"all": ("main/admin.css", "main/publication-editor.css")}


@admin.register(FormResult)
class FormResultAdmin(admin.ModelAdmin):
    # ищем анкеты по нику и почте
    list_display = ("myname", "status", "gender", "email", "step", "timezone_name", "play_schedule")
    list_display_links = ("myname",)
    search_fields = ("myname", "email")
    list_filter = ("status", "gender", "birthdate")
    fieldsets = (("Анкета", {"fields": ("myname", "step", "gender", "email", "birthdate", "steam_id", "timezone_name", "play_schedule")} ), ("Рассмотрение", {"fields": ("status", "admin_comment")}))
    ordering = ("myname",)
    list_per_page = 25

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # тут редактируются контакты
    list_display = ("name", "email")
    list_display_links = ("name",)
    search_fields = ("name", "email")
    ordering = ("name",)
    list_per_page = 25

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    # управляем игроками на сайте
    list_display = ("display_name", "position", "mmr", "status", "is_active", "joined_at")
    list_display_links = ("display_name",)
    search_fields = ("name", "nickname", "favorite_heroes")
    list_filter = ("position", "status", "is_active")
    ordering = ("name",)
    list_per_page = 25

    class Media:
        css = {"all": ("main/admin.css",)}

    @admin.display(description="Игрок")
    def display_name(self, obj):
        return obj.display_name


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # категории товаров
    list_display = ("name", "category")
    list_display_links = ("name",)
    search_fields = ("name", "category")
    list_filter = ("category",)
    ordering = ("name",)
    list_per_page = 25

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.action(description="Отметить выбранные товары как имеющиеся")
def mark_available(modeladmin, request, queryset):
    # меняем выбранные товары одним запросом
    queryset.update(nalichie=True)


@admin.action(description="Отметить выбранные товары как отсутствующие")
def mark_unavailable(modeladmin, request, queryset):
    # временно убираем товары из наличия
    queryset.update(nalichie=False)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = (ProductVariantInline, ProductPhotoInline)
    # цену остаток и наличие можно менять прямо в списке
    list_display = (
        "name", "sale", "material", "data_prod",
        "counter", "nalichie", "cat_id",
    )
    list_display_links = ("name",)
    search_fields = ("name", "material", "cat_id__name")
    fieldsets = (
        ("Товар", {"fields": ("name", "description", "sizes", "sale", "material", "data_prod", "counter", "nalichie", "cat_id")}),
        ("Фотография", {"fields": ("image_url", "image_source")}),
    )
    list_filter = ("nalichie", "material", "cat_id", "data_prod")
    list_editable = ("sale", "counter", "nalichie")
    ordering = ("name",)
    list_per_page = 25
    actions = (mark_available, mark_unavailable)

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.register(GuildEvent)
class GuildEventAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        old = GuildEvent.objects.select_for_update().get(pk=obj.pk) if change else None
        super().save_model(request, obj, form, change)
        if old:
            from django.utils import timezone
            if (obj.is_cancelled or not obj.is_published) and old.is_published and not old.is_cancelled:
                text = f'Событие «{obj.title}» отменено или снято с публикации.'
                url = reverse('account') + '#my-events'
            elif obj.is_published and not obj.is_cancelled and old.starts_at != obj.starts_at:
                text = f'Перенос: {obj.title[:100]}. Было {timezone.localtime(old.starts_at):%d.%m.%Y %H:%M %Z}, теперь {timezone.localtime(obj.starts_at):%d.%m.%Y %H:%M %Z}. Можно отменить запись.'
                url = reverse('events') + f'#event-{obj.pk}'
            else:
                return
            accounts = obj.registrations.exclude(account=None).order_by().values_list('account_id', flat=True).distinct()
            Notification.objects.bulk_create([Notification(account_id=pk, text=text, url=url) for pk in accounts])
    list_display = ("title", "starts_at", "format", "capacity", "is_published", "is_cancelled")
    list_filter = ("is_published", "is_cancelled", "format")
    search_fields = ("title", "description")
    date_hierarchy = "starts_at"

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "nickname", "contact", "is_waiting", "created_at")
    list_filter = ("event",)
    search_fields = ("nickname", "contact")


@admin.register(PartyListing)
class PartyListingAdmin(admin.ModelAdmin):
    list_display = ("nickname", "role", "mmr_min", "mmr_max", "schedule", "goal", "is_active", "expires_at")
    list_filter = ("role", "goal", "microphone", "is_active")
    search_fields = ("nickname", "contact", "schedule")
    list_editable = ("is_active",)

    class Media:
        css = {"all": ("main/admin.css",)}


@admin.register(PartyResponse)
class PartyResponseAdmin(admin.ModelAdmin):
    list_display = ("listing", "nickname", "role", "is_accepted", "contact", "created_at")
    readonly_fields = ('is_accepted',)
    search_fields = ("nickname", "contact", "message")


class MerchOrderItemInline(admin.TabularInline):
    model = MerchOrderItem
    extra = 0
    readonly_fields = ("product", "name", "size", "quantity", "price")


@admin.register(MerchOrder)
class MerchOrderAdmin(admin.ModelAdmin):
    list_display = ("__str__", "name", "contact", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "contact", "delivery")
    inlines = (MerchOrderItemInline,)
    readonly_fields = ("created_at", "total", "stock_returned")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, 'status') if obj and obj.status == 'cancelled' else fields

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            status = obj.status
            obj.status = MerchOrder.objects.get(pk=obj.pk).status
            super().save_model(request, obj, form, change)
            updated = change_order_status(obj.pk, status)
            obj.status = updated.status
            obj.stock_returned = updated.stock_returned
        else:
            super().save_model(request, obj, form, change)

    class Media:
        css = {"all": ("main/admin.css",)}


class PollChoiceInline(admin.TabularInline):
    model = PollChoice
    extra = 2


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    inlines = (PollChoiceInline,)
    list_display = ('title', 'closes_at', 'is_published')


class TournamentMatchInline(admin.TabularInline):
    model = TournamentMatch
    extra = 0


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    inlines = (TournamentMatchInline,)
    list_display = ('title', 'starts_at', 'registration_ends_at', 'is_published')
    search_fields = ('title',)


admin.site.register(Achievement)
admin.site.register(PlayerAchievement)
from .models import MatchMoment


class MomentInline(admin.TabularInline):
    model = MatchMoment
    extra = 0


@admin.register(MatchReport)
class MatchReportAdmin(admin.ModelAdmin):
    inlines = (MomentInline,)
    list_display = ('title', 'played_at', 'won', 'is_published', 'tournament_match')
    list_filter = ('is_published', 'won')
    search_fields = ('title', 'roster')
    filter_horizontal = ('players',)


@admin.register(TournamentTeam)
class TournamentTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament', 'captain')
    filter_horizontal = ('players',)
