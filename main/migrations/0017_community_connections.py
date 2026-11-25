from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('main', '0016_existing_cancelled_orders')]

    operations = [
        migrations.AddField(model_name='person', name='goal', field=models.CharField(
            choices=[('rating', 'Поднять рейтинг'), ('fun', 'Обычные игры'), ('team', 'Постоянный состав')],
            default='team', max_length=20, verbose_name='Цель игры')),
        migrations.AddField(model_name='matchreport', name='players', field=models.ManyToManyField(
            blank=True, related_name='match_reports', to='main.person', verbose_name='Игроки')),
        migrations.AddField(model_name='matchreport', name='tournament_match', field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports',
            to='main.tournamentmatch', verbose_name='Матч турнира')),
        migrations.AddField(model_name='tournamentteam', name='players', field=models.ManyToManyField(
            blank=True, related_name='tournament_teams', to='main.person', verbose_name='Профили игроков')),
        migrations.AddField(model_name='tournamentmatch', name='starts_at', field=models.DateTimeField(
            blank=True, null=True, verbose_name='Время матча')),
    ]
