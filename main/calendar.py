from datetime import timedelta
from django.http import HttpResponse
from django.utils import timezone


def calendar_response(uid, title, start, description='', end=None):
    def text(value):
        return str(value).replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')

    def stamp(value):
        from datetime import timezone as dt_timezone
        return value.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//vetmo//Community//RU', 'BEGIN:VEVENT',
             f'UID:{uid}@vetmo', f'DTSTAMP:{stamp(timezone.now())}', f'DTSTART:{stamp(start)}',
             f'DTEND:{stamp(end or start + timedelta(hours=2))}', f'SUMMARY:{text(title)}',
             f'DESCRIPTION:{text(description)}', 'END:VEVENT', 'END:VCALENDAR']
    # RFC 5545: fold at 75 octets, without splitting a UTF-8 character.
    folded = []
    for line in lines:
        chunk = ''
        for char in line:
            if len((chunk + char).encode('utf-8')) > 75:
                folded.append(chunk)
                chunk = ' '
            chunk += char
        folded.append(chunk)
    response = HttpResponse('\r\n'.join(folded) + '\r\n', content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="vetmo-event.ics"'
    return response
