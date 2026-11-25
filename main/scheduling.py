from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone


def player_zone(person):
    try:
        return ZoneInfo(person.timezone_name or 'Europe/Moscow')
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo('Europe/Moscow')


def intervals(person, now=None):
    if not person or not person.play_days or not person.play_from or not person.play_until:
        return []
    zone = player_zone(person)
    today = (now or timezone.now()).astimezone(zone).date()
    days = {str(day) for day in person.play_days}
    result = []
    for offset in range(-1, 8):
        day = today + timedelta(days=offset)
        if str(day.weekday()) not in days:
            continue
        start = datetime.combine(day, person.play_from, tzinfo=zone)
        end = datetime.combine(day, person.play_until, tzinfo=zone)
        if end <= start:
            end += timedelta(days=1)
        result.append((start.astimezone(ZoneInfo('UTC')), end.astimezone(ZoneInfo('UTC'))))
    return result


def available_window(captain, viewer=None, bounds=None, now=None):
    now = now or timezone.now()
    other = intervals(viewer, now) if viewer else [(now, now + timedelta(days=9))]
    lower, upper = bounds or (now, now + timedelta(days=9))
    for a, b in intervals(captain, now):
        for c, d in other:
            start, end = max(a, c, now, lower), min(b, d, upper)
            if end - start >= timedelta(minutes=30):
                return start, end


def overlap_reason(first, second):
    window = available_window(second, first) if first else None
    if window:
        local, finish = (t.astimezone(player_zone(first)) for t in window)
        return f'Есть общее время: {local:%d.%m с %H:%M} до {finish:%d.%m %H:%M} ({player_zone(first).key}). Это окно доступности, не назначенная игра.'
    return ''


def recruiting_roles(listing):
    occupied = {listing.captain_role} | {r.role for r in listing.responses.all() if r.is_accepted}
    return [role for role, _ in listing.ROLE_CHOICES[1:] if role not in occupied and listing.role in ('Любая', role)]


def party_reasons(person, listing):
    if not person:
        return []
    reasons = []
    roles = recruiting_roles(listing)
    if person.position in roles:
        reasons.append('Твоя позиция свободна')
    elif person.backup_position in roles:
        reasons.append('Свободна твоя запасная позиция')
    if person.mmr is not None and (listing.mmr_min is None or person.mmr >= listing.mmr_min) and (listing.mmr_max is None or person.mmr <= listing.mmr_max):
        reasons.append('Подходит по диапазону MMR')
    captain = getattr(listing.account, 'player_profile', None) if listing.account_id else None
    common = overlap_reason(person, captain) if captain and captain.is_active and captain.is_public else ''
    if common:
        reasons.append(common)
    return reasons
