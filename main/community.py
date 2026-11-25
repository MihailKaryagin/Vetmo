from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import TournamentTeamForm, EmailChangeForm
from .models import (EventRegistration, GuildEvent, Notification, PartyListing, PartyResponse,
                     Favorite, Person, Product, MatchReport, Tournament, TournamentMatch, TournamentTeam, Poll, PollChoice, PollVote)
from .services import limit_posts, change_order_status
from .views import owns_listing


CONFIRM_PREFIX = 'Капитан назначил игру:'
REMINDER_PREFIX = 'Скоро игра:'


def clear_game_notices(listing):
    """Caller holds the listing lock; messages for a previous start no longer apply."""
    Notification.objects.filter(url=reverse('party_detail', args=[listing.pk])).filter(
        Q(text__startswith=CONFIRM_PREFIX) | Q(text__startswith=REMINDER_PREFIX)
    ).delete()


def refresh_response_notice(listing, role, *, new=False):
    if not listing.account_id:
        return
    url = reverse('party_detail', args=[listing.pk])
    prefix = f'Отклики · {role or "без позиции"}: '
    notices = Notification.objects.filter(account_id=listing.account_id, url=url, is_read=False, text__startswith=prefix)
    count = listing.responses.filter(role=role, is_accepted=False, removed_at=None).count()
    if not count:
        notices.update(text=f'{prefix}все рассмотрены', is_read=True)
        return
    text = f'{prefix}{count} ждут ответа'
    if not notices.update(text=text, **({'created_at': timezone.now()} if new else {})) and new:
        Notification.objects.create(account_id=listing.account_id, text=text, url=url)


@login_required
@require_POST
@limit_posts
def account_email(request):
    form = EmailChangeForm(request.POST)
    if form.is_valid():
        if request.user.check_password(form.cleaned_data['password']):
            request.user.email = form.cleaned_data['email']
            request.user.save(update_fields=['email'])
            messages.success(request, 'Почта сохранена')
            return redirect('account')
        else:
            form.add_error('password', 'Текущий пароль не подходит')
    from .views import account
    return account(request, email_form=form)


@require_POST
@limit_posts
@transaction.atomic
def event_cancel(request, pk):
    event = get_object_or_404(GuildEvent.objects.select_for_update(), pk=pk)
    registrations = event.registrations.filter(account=request.user) if request.user.is_authenticated else event.registrations.filter(visitor_key=request.session.get('community_key', '__none__'), account__isnull=True)
    registration = registrations.first()
    if not registration:
        return HttpResponseForbidden('Это не ваша регистрация')
    if event.starts_at <= timezone.now():
        messages.error(request, 'Событие уже началось')
        return redirect('events')
    registration.delete()
    # очередь двигаем под блокировкой события
    while event.is_published and not event.is_cancelled and event.registered_count < event.capacity:
        waiting = event.registrations.filter(is_waiting=True).order_by('created_at', 'pk').first()
        if not waiting:
            break
        waiting.is_waiting = False
        waiting.save(update_fields=['is_waiting'])
        if waiting.account_id:
            Notification.objects.create(account=waiting.account, text=f'Освободилось место на {event.title}'[:255], url=reverse('events'))
    messages.success(request, 'Регистрация отменена')
    return redirect('events')


@require_POST
@transaction.atomic
def party_accept(request, pk, response_pk):
    listing = get_object_or_404(PartyListing.objects.select_for_update(), pk=pk)
    if not owns_listing(request, listing):
        return HttpResponseForbidden('Только автор может менять состав')
    response = get_object_or_404(PartyResponse, pk=response_pk, listing=listing)
    if response.removed_at:
        messages.error(request, 'Этот отклик уже завершён.')
        return redirect('party_detail', pk=pk)
    if response.is_accepted:
        response.is_accepted = False
        response.removed_at = timezone.now()
    elif not listing.is_active or listing.expires_at <= timezone.now():
        messages.error(request, 'Набор закрыт')
        return redirect('party_detail', pk=pk)
    elif not response.role or response.role == listing.captain_role or listing.responses.filter(is_accepted=True, role=response.role).exists() or listing.responses.filter(is_accepted=True).count() >= 4:
        messages.error(request, 'Позиция уже занята или не указана')
        return redirect('party_detail', pk=pk)
    else:
        response.is_accepted = True
        response.accepted_at = timezone.now()
        response.removed_at = None
    response.save(update_fields=['is_accepted', 'accepted_at', 'removed_at'])
    refresh_response_notice(listing, response.role)
    if listing.game_at:
        clear_game_notices(listing)
        listing.game_at = None
        listing.save(update_fields=['game_at'])
        listing.responses.update(confirmed_at=None, reminded_for=None)
        for member in listing.responses.filter(account__isnull=False, is_accepted=True).exclude(pk=response.pk):
            Notification.objects.create(account_id=member.account_id, text='Состав изменился. Капитан назначит новое время игры.', url=reverse('party_detail', args=[pk]))
    if response.account_id:
        Notification.objects.create(account=response.account, text='Состав пати обновлён проверь свою позицию', url=reverse('party_detail', args=[pk]))
    return redirect('party_detail', pk=pk)


@login_required
@require_POST
def favorite_toggle(request, kind, pk):
    models = {'person': (Person, {'is_active': True, 'is_public': True}), 'listing': (PartyListing, {'is_active': True, 'expires_at__gt': timezone.now()}), 'product': (Product, {})}
    if kind not in models:
        return HttpResponseForbidden()
    model, filters = models[kind]
    obj = get_object_or_404(model, pk=pk, **filters)
    favorite, created = Favorite.objects.get_or_create(account=request.user, **{kind: obj})
    if not created:
        favorite.delete()
    return redirect('favorites')


@login_required
def favorites(request):
    rows = Favorite.objects.filter(account=request.user).select_related('person', 'listing', 'product')
    return render(request, 'main/favorites.html', {'favorites': rows, 'now': timezone.now()})


@login_required
@require_POST
def favorite_remove(request, pk):
    get_object_or_404(Favorite, pk=pk, account=request.user).delete()
    return redirect('favorites')


@login_required
def notification_count(request):
    return JsonResponse({'count': request.user.notifications.filter(is_read=False).count()})


def matches(request):
    return render(request, 'main/matches.html', {'reports': MatchReport.objects.filter(is_published=True,
        played_at__lte=timezone.now()).prefetch_related('players').select_related('tournament_match__tournament')[:50]})


def todays_series(now):
    local = timezone.localtime(now)
    start = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo)
    public_reports = MatchReport.objects.filter(is_published=True, played_at__lte=now)
    return TournamentMatch.objects.filter(tournament__is_published=True, starts_at__gte=start,
        starts_at__lt=start + timedelta(days=1)).select_related('team_a', 'team_b', 'tournament').prefetch_related(
        Prefetch('reports', queryset=public_reports)).order_by('starts_at', 'pk')


def tournaments(request):
    return render(request, 'main/tournaments.html', {'tournaments': Tournament.objects.filter(is_published=True)
        .prefetch_related('matches__team_a', 'matches__team_b').order_by('-starts_at')})


@limit_posts
def tournament_detail(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, is_published=True)
    form = TournamentTeamForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        with transaction.atomic():
            tournament = Tournament.objects.select_for_update().get(pk=pk)
            if tournament.registration_ends_at <= timezone.now():
                messages.error(request, 'Регистрация закрыта')
            elif form.is_valid():
                if tournament.teams.filter(name=form.cleaned_data['name']).exists() or tournament.teams.filter(captain=request.user).exists():
                    form.add_error(None, 'Команда или капитан уже зарегистрированы')
                else:
                    team = form.save(commit=False)
                    team.tournament = tournament
                    team.captain = request.user
                    team.save()
                    messages.success(request, 'Команда зарегистрирована. Состав появился в списке участников, пары объявим после закрытия регистрации.')
                    return redirect('tournament_detail', pk=pk)
    teams = list(tournament.teams.prefetch_related('players'))
    matches = list(tournament.matches.select_related('team_a', 'team_b'))
    my_teams = {team.pk for team in teams if request.user.is_authenticated and (
        team.captain_id == request.user.pk or any(p.account_id == request.user.pk for p in team.players.all()))}
    upcoming = [m for m in matches if not m.is_finished and (not my_teams or {m.team_a_id, m.team_b_id} & my_teams)]
    next_match = min(upcoming, key=lambda m: (m.starts_at is None, m.starts_at, m.round, m.pk), default=None)
    standings = {team.pk: {'team': team, 'wins': 0, 'played': 0} for team in teams}
    for match in matches:
        if not match.is_finished:
            continue
        for team_id in (match.team_a_id, match.team_b_id):
            standings[team_id]['played'] += 1
        standings[match.team_a_id if match.score_a > match.score_b else match.team_b_id]['wins'] += 1
    return render(request, 'main/tournament_detail.html', {'tournament': tournament, 'teams': teams, 'matches': matches,
        'next_match': next_match, 'my_team': bool(my_teams),
        'reports': MatchReport.objects.filter(tournament_match__tournament=tournament, is_published=True, played_at__lte=timezone.now()),
        'form': form, 'standings': sorted(standings.values(), key=lambda row: -row['wins']), 'now': timezone.now()})


def polls(request):
    rows = Poll.objects.filter(is_published=True).prefetch_related(Prefetch('choices',
        queryset=PollChoice.objects.annotate(total=Count('votes')).order_by('pk'), to_attr='results'))
    voted = set(PollVote.objects.filter(account=request.user).values_list('poll_id', flat=True)) if request.user.is_authenticated else set()
    for poll in rows:
        poll.has_voted = poll.pk in voted
    return render(request, 'main/polls.html', {'polls': rows, 'now': timezone.now()})


@login_required
@require_POST
@limit_posts
@transaction.atomic
def poll_vote(request, pk):
    poll = get_object_or_404(Poll.objects.select_for_update(), pk=pk, is_published=True)
    if poll.closes_at <= timezone.now():
        messages.error(request, 'Голосование завершено')
    else:
        choice_id = request.POST.get('choice', '')
        if not choice_id.isdecimal() or len(choice_id) > 18:
            messages.error(request, 'Выбери вариант ответа')
            return redirect('polls')
        choice = get_object_or_404(PollChoice, pk=choice_id, poll=poll)
        PollVote.objects.get_or_create(poll=poll, account=request.user, defaults={'choice': choice})
    return redirect('polls')


@login_required
@require_POST
def order_cancel(request, pk):
    from .models import MerchOrder
    with transaction.atomic():
        order = get_object_or_404(MerchOrder.objects.select_for_update(), pk=pk, account=request.user)
        if order.status not in ('new', 'cancelled'):
            messages.error(request, 'Для отмены подтвержденного заказа свяжитесь с поддержкой')
        else:
            change_order_status(order.pk, 'cancelled')
            messages.success(request, 'Заказ отменён остатки возвращены')
    return redirect('account_order', pk=pk)
