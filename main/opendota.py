import json
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.db import IntegrityError
from django.utils import timezone


def update_match(report, match_id):
    if not isinstance(match_id, int) or not 1 <= match_id <= 9223372036854775807:
        raise ValueError('Некорректный ID матча')
    request = Request(f'https://api.opendota.com/api/matches/{match_id}', headers={'User-Agent': 'vetmo/1.0', 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=12) as response:
            payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError('Ответ OpenDota слишком большой')
        data = json.loads(payload)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise ValueError('OpenDota недоступна. Попробуй позже; сохранённые данные не изменены.') from error
    if not isinstance(data, dict) or data.get('match_id') != match_id or not isinstance(data.get('duration'), int):
        raise ValueError('OpenDota ещё не располагает данными этого матча')
    keys = ('match_id', 'duration', 'radiant_win', 'radiant_score', 'dire_score', 'start_time', 'game_mode', 'lobby_type')
    stats = {key: data.get(key) for key in keys}
    players = data.get('players')
    if not isinstance(players, list):
        raise ValueError('OpenDota вернула неполные данные игроков')
    stats['players'] = [{key: player.get(key) for key in ('player_slot', 'hero_id', 'kills', 'deaths', 'assists', 'gold_per_min', 'xp_per_min')}
                        for player in players[:10] if isinstance(player, dict)]
    report.match_id = match_id
    report.duration = max(0, data['duration'])
    report.match_stats = stats
    report.stats_updated_at = timezone.now()
    try:
        report.save(update_fields=['match_id', 'duration', 'match_stats', 'stats_updated_at'])
    except IntegrityError as error:
        raise ValueError('Этот ID уже привязан к другому разбору') from error
