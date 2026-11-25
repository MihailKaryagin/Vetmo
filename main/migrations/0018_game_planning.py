from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('main', '0017_community_connections')]
    operations = [
        migrations.AddField(model_name='person', name='play_days', field=models.JSONField(blank=True, default=list, verbose_name='Дни игры (0 — понедельник)')),
        migrations.AddField(model_name='person', name='play_from', field=models.TimeField(blank=True, null=True, verbose_name='Играю с')),
        migrations.AddField(model_name='person', name='play_until', field=models.TimeField(blank=True, null=True, verbose_name='Играю до')),
        migrations.AddField(model_name='partylisting', name='game_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Подтверждённый старт')),
        migrations.AddField(model_name='partyresponse', name='confirmed_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Участие подтверждено')),
        migrations.AddField(model_name='matchreport', name='match_id', field=models.PositiveBigIntegerField(blank=True, null=True, unique=True, verbose_name='ID матча Dota 2')),
        migrations.AddField(model_name='matchreport', name='duration', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Продолжительность, секунд')),
        migrations.AddField(model_name='matchreport', name='key_moment', field=models.TextField(blank=True, verbose_name='Ключевой момент')),
        migrations.AddField(model_name='matchreport', name='went_well', field=models.TextField(blank=True, verbose_name='Что получилось')),
        migrations.AddField(model_name='matchreport', name='next_steps', field=models.TextField(blank=True, verbose_name='На следующую игру')),
        migrations.AddField(model_name='matchreport', name='match_stats', field=models.JSONField(blank=True, default=dict, verbose_name='Статистика OpenDota')),
        migrations.AddField(model_name='matchreport', name='stats_updated_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Статистика обновлена')),
    ]
