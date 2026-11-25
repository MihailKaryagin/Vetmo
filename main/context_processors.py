def notifications(request):
    count = request.user.notifications.filter(is_read=False).count() if request.user.is_authenticated else 0
    return {'unread_notifications': count}
