from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .calendar import calendar_response
from .community import CONFIRM_PREFIX, clear_game_notices
from .forms import PartyStartForm
from .models import GuildEvent, MatchReport, Notification, PartyListing
from .services import limit_posts
from .views import owns_listing


def match_detail(request, pk):
    report = get_object_or_404(MatchReport.objects.prefetch_related('players').select_related('tournament_match__tournament'),
                               pk=pk, is_published=True, played_at__lte=timezone.now())
    related = MatchReport.objects.filter(topic=report.topic, is_published=True, played_at__lte=timezone.now()).exclude(pk=pk)[:4] if report.topic else []
    return render(request, 'main/match_detail.html', {'report': report, 'related_reports': related})


@permission_required('main.change_matchreport', raise_exception=True)
@require_POST
@limit_posts
def match_refresh(request, pk):
    from .opendota import update_match
    report = get_object_or_404(MatchReport, pk=pk)
    try:
        match_id = request.POST.get('match_id', '')
        if not match_id.isdecimal() or len(match_id) > 19:
            raise ValueError('Укажи числовой ID матча Dota 2')
        update_match(report, int(match_id))
        messages.success(request, 'Статистика OpenDota обновлена')
    except ValueError as error:
        messages.error(request, str(error))
    return redirect('match_detail', pk=pk)


@require_POST
@limit_posts
@transaction.atomic
def party_start(request, pk):
    listing = get_object_or_404(PartyListing.objects.select_for_update(), pk=pk)
    if not owns_listing(request, listing):
        return HttpResponseForbidden('Только капитан назначает игру')
    form = PartyStartForm(request.POST)
    responses = list(listing.responses.filter(is_accepted=True))
    roles = {listing.captain_role} | {r.role for r in responses}
    if not listing.is_active or listing.expires_at <= timezone.now():
        messages.error(request, 'Набор уже закрыт')
    elif len(responses) != 4 or len(roles) != 5:
        messages.error(request, 'Сначала собери пять разных позиций')
    elif not form.is_valid():
        from .views import party_detail
        return party_detail(request, pk, start_form=form)
    else:
        new_time = form.cleaned_data['game_at']
        if listing.game_at != new_time:
            clear_game_notices(listing)
            listing.game_at = new_time
            listing.save(update_fields=['game_at'])
            listing.responses.update(confirmed_at=None, reminded_for=None)
            for response in responses:
                if response.account_id:
                    Notification.objects.create(account_id=response.account_id,
                        text=f'{CONFIRM_PREFIX} {listing.nickname}. Подтверди участие.', url=reverse('party_detail', args=[pk]))
            messages.success(request, 'Игра назначена. Участникам отправлены уведомления; гости увидят время в объявлении.')
    return redirect('party_detail', pk=pk)


@require_POST
@transaction.atomic
def party_confirm(request, pk):
    listing = get_object_or_404(PartyListing.objects.select_for_update(), pk=pk)
    if not listing.game_at or listing.game_at <= timezone.now() or not listing.is_active:
        messages.error(request, 'Нет предстоящей игры для подтверждения')
        return redirect('party_detail', pk=pk)
    identity = {'account': request.user} if request.user.is_authenticated else {
        'visitor_key': request.session.get('community_key', '__none__'), 'account__isnull': True}
    response = get_object_or_404(listing.responses, is_accepted=True, **identity)
    if response.confirmed_at is None:
        response.confirmed_at = timezone.now()
        response.save(update_fields=['confirmed_at'])
        if response.account_id:
            Notification.objects.filter(account_id=response.account_id, url=reverse('party_detail', args=[pk]), text__startswith=CONFIRM_PREFIX).update(text='Время игры подтверждено.', is_read=True)
        if listing.account_id:
            Notification.objects.create(account_id=listing.account_id, text=f'{response.nickname} подтвердил участие', url=reverse('party_detail', args=[pk]))
    messages.success(request, 'Участие подтверждено. Увидимся в игре!')
    return redirect('party_detail', pk=pk)


def event_calendar(request, pk):
    event = get_object_or_404(GuildEvent, pk=pk, is_published=True, is_cancelled=False)
    return calendar_response(f'event-{pk}', event.title, event.starts_at, event.description, event.ends_at)


def party_calendar(request, pk):
    listing = get_object_or_404(PartyListing, pk=pk, is_active=True, game_at__gt=timezone.now())
    allowed = owns_listing(request, listing)
    if not allowed:
        identity = {'account': request.user} if request.user.is_authenticated else {
            'visitor_key': request.session.get('community_key', '__none__'), 'account__isnull': True}
        allowed = listing.responses.filter(is_accepted=True, **identity).exists()
    if not allowed:
        return HttpResponseForbidden('Календарь доступен участникам состава')
    return calendar_response(f'party-{pk}', f'Пати {listing.nickname}', listing.game_at, listing.contact)


def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    # This page is deliberately independent of database-backed context processors.
    from django.template.loader import get_template
    from django.http import HttpResponse
    return HttpResponse(get_template('500.html').render({}), status=500)
