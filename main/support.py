"""Session-scoped website support API shared with the operator's admin chat."""
import json
import uuid
from datetime import timedelta

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from .models import SupportConversation, SupportMessage


@ensure_csrf_cookie
@never_cache
@require_http_methods(['GET', 'POST'])
def messages(request):
    if request.method == 'GET':
        try:
            after = max(0, int(request.GET.get('after', '0')))
            if after > 9223372036854775807:
                raise ValueError
        except ValueError:
            return JsonResponse({'error': 'Некорректный номер сообщения.'}, status=400)
        conversation_id = request.session.get('support_conversation')
        conversation = SupportConversation.objects.filter(pk=conversation_id).first() if conversation_id else None
        revision = conversation.revision if conversation else 0
        if request.GET.get('revision', str(revision)) != str(revision):
            after = 0
        rows = conversation.messages.filter(pk__gt=after)[:100] if conversation else []
        return JsonResponse({'revision': revision, 'is_closed': bool(conversation and conversation.is_closed), 'messages': [
            {'id': row.pk, 'text': row.text, 'from_operator': row.from_operator,
             'created_at': row.created_at.isoformat(), 'color': row.color} for row in rows
        ]})

    try:
        if len(request.body) > 16000:
            raise ValueError
        data = json.loads(request.body)
        text = data.get('text') if isinstance(data, dict) else None
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError
        text = text.strip()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Введите сообщение от 1 до 2000 символов.'}, status=400)

    conversation_id = request.session.get('support_conversation')
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        request.session['support_conversation'] = conversation_id
    with transaction.atomic():
        conversation, _ = SupportConversation.objects.get_or_create(pk=conversation_id)
        conversation = SupportConversation.objects.select_for_update().get(pk=conversation.pk)
        if conversation.is_closed:
            return JsonResponse({'error': 'Диалог закрыт оператором.'}, status=409)
        recent = conversation.messages.filter(from_operator=False, created_at__gte=timezone.now() - timedelta(minutes=1))
        if recent.count() >= 10:
            return JsonResponse({'error': 'Слишком много сообщений. Подождите минуту.'}, status=429)
        message = conversation.messages.create(text=text)
    return JsonResponse({'id': message.pk}, status=201)
