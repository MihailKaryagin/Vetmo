from django.db import migrations


def preserve_existing_cancellations(apps, schema_editor):
    # старые отмены не возвращаем повторно потому что склад могли поправить вручную
    apps.get_model('main', 'MerchOrder').objects.using(schema_editor.connection.alias).filter(status='cancelled').update(stock_returned=True)


class Migration(migrations.Migration):
    dependencies = [('main', '0015_achievement_formthrottle_matchreport_poll_tournament_and_more')]
    operations = [migrations.RunPython(preserve_existing_cancellations, migrations.RunPython.noop)]
