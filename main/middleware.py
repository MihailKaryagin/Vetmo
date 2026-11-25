from django.utils import timezone
from .scheduling import player_zone


class PlayerTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        person = getattr(request.user, 'player_profile', None) if request.user.is_authenticated else None
        with timezone.override(player_zone(person) if person else 'Europe/Moscow'):
            return self.get_response(request)
