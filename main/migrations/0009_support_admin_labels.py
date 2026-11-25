from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('main', '0008_support_chat')]
    operations = [migrations.AlterModelOptions(
        name='supportconversation',
        options={'verbose_name': 'Диалог поддержки', 'verbose_name_plural': 'Поддержка — диалоги'},
    )]
