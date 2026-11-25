from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PartyFilterForm
from .models import Notification, PartyListing, PartyResponse, SavedPartySearch, party_expiry
from django.db.models import Q
from .scheduling import available_window, recruiting_roles


def evening_bounds(data, now):
    now = timezone.localtime(now)
    start = datetime.combine(now.date(), data.get('evening_from') or time(18), now.tzinfo)
    end = datetime.combine(now.date(), data.get('evening_to') or time(23), now.tzinfo)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def search_windows(data, now):
    if data.get('evening'):
        windows = [evening_bounds(data, now)]
    elif data.get('days') or data.get('after'):
        midnight = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        windows = [(midnight + timedelta(days=i), midnight + timedelta(days=i+1)) for i in range(8)]
    else:
        return [None]
    result = []
    for start, end in windows:
        if data.get('days') and str(start.weekday()) not in data['days']:
            continue
        if data.get('after'):
            start = max(start, datetime.combine(start.date(), data['after'], start.tzinfo))
        result.append((start, end))
    return result


def search_parties(data, viewer, now, *, recommend=False, request=None):
    listings = PartyListing.objects.filter(is_active=True, expires_at__gt=now, game_at__isnull=True).select_related('account__player_profile').prefetch_related('responses')
    if recommend and request.user.is_authenticated:
        listings = listings.exclude(account=request.user).exclude(responses__account=request.user)
    if recommend and request.session.get('community_key'):
        key = request.session['community_key']
        listings = listings.exclude(visitor_key=key, account__isnull=True).exclude(responses__in=PartyResponse.objects.filter(visitor_key=key, account__isnull=True))
    if data.get('q'):
        listings = listings.filter(Q(nickname__icontains=data['q']) | Q(schedule__icontains=data['q']))
    for field in ('mode', 'goal', 'microphone'):
        if data.get(field):
            listings = listings.filter(**{field: data[field]})
    if data.get('schedule'):
        listings = listings.filter(schedule__icontains=data['schedule'])
    mmr = viewer.mmr if recommend and viewer else data.get('mmr')
    if mmr is not None:
        listings = listings.filter(Q(mmr_min=None) | Q(mmr_min__lte=mmr), Q(mmr_max=None) | Q(mmr_max__gte=mmr))
    windows = search_windows(data, now)
    common = data.get('compatible') or (recommend and viewer and viewer.play_days and viewer.play_from and viewer.play_until)
    if common and not viewer:
        return []
    result = []
    for item in listings.iterator(chunk_size=200):
        item.open_roles = recruiting_roles(item)
        role = data.get('role')
        if not item.open_roles or (role == 'Любая' and item.role != role) or (role and role != 'Любая' and role not in item.open_roles):
            continue
        item.rank = 0 if viewer and viewer.position in item.open_roles else 1 if viewer and viewer.backup_position in item.open_roles else 2
        if recommend and viewer and (viewer.position or viewer.backup_position) and item.rank == 2:
            continue
        captain = getattr(item.account, 'player_profile', None)
        item.window = None
        if captain and captain.is_public and captain.is_active:
            for bounds in windows:
                item.window = available_window(captain, viewer if common else None, bounds, now)
                if item.window:
                    break
        if (windows != [None] or common) and not item.window:
            continue
        item.members = sum(r.is_accepted for r in item.responses.all())
        result.append(item)
    result.sort(key=lambda item: (item.rank, not item.window, item.window[0] if item.window else now))
    return result


@login_required
@require_POST
def save_search(request):
    name = request.POST.get('name', '').strip()[:80]
    query = QueryDict(request.POST.get('query', '')[:2000]).copy()
    for key in list(query):
        if key not in PartyFilterForm.base_fields:
            del query[key]
    if name and PartyFilterForm(query).is_valid():
        SavedPartySearch.objects.update_or_create(account=request.user, name=name, defaults={'query': query.urlencode()})
        messages.success(request, 'Поиск сохранён в кабинете.')
    return redirect('account')


@require_POST
@transaction.atomic
def roster_action(request, pk, action):
    from .views import owns_listing
    old = get_object_or_404(PartyListing.objects.select_for_update(), pk=pk)
    if not owns_listing(request, old):
        return HttpResponseForbidden('Только для капитана')
    if action == 'decline':
        from .community import refresh_response_notice
        try:
            response_pk = int(request.POST.get('response', ''))
        except ValueError:
            from django.http import Http404
            raise Http404
        response = get_object_or_404(old.responses, pk=response_pk, is_accepted=False, removed_at=None)
        response.removed_at = timezone.now()
        response.save(update_fields=['removed_at'])
        refresh_response_notice(old, response.role)
        if response.account_id:
            Notification.objects.create(account_id=response.account_id, text='Капитан отклонил отклик.', url=reverse('party_detail', args=[old.pk]))
    elif action == 'again' and old.game_at and old.game_at <= timezone.now():
        members = list(old.responses.filter(is_accepted=True, account__isnull=False))
        old.pk = None
        old.game_at = None
        old.role = 'Любая'
        old.is_active = True
        old.detail_views = 0
        old.expires_at = party_expiry()
        old.save(force_insert=True)
        for member in members:
            Notification.objects.create(account_id=member.account_id, text=f'{old.nickname} приглашает сыграть ещё раз. Откликнись, если свободен.', url=reverse('party_detail', args=[old.pk]))
    elif action == 'renew':
        old.expires_at = timezone.now() + timedelta(days=7)
        old.is_active = True
        old.save(update_fields=['expires_at', 'is_active'])
    elif action == 'replacement':
        role = request.POST.get('role')
        if role in dict(PartyListing.ROLE_CHOICES[1:]) and role != old.captain_role and not old.responses.filter(role=role, is_accepted=True).exists():
            old.role, old.expires_at, old.is_active = role, party_expiry(), True
            old.save(update_fields=['role', 'expires_at', 'is_active'])
    return redirect('party_detail', pk=old.pk)


def game_day(request):
    from .community import todays_series
    now = timezone.now()
    return render(request, 'main/game_day.html', {'matches': todays_series(now), 'now': now})


def upcoming_games(user):
    return PartyResponse.objects.filter(account=user, is_accepted=True, listing__is_active=True, listing__game_at__gt=timezone.now()).select_related('listing').order_by('listing__game_at')
