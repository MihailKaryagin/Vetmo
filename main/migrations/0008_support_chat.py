import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('main', '0007_correct_merch_photos')]
    operations = [
        migrations.CreateModel(name='SupportConversation', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name='SupportBotState', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('offset', models.BigIntegerField(default=0)),
        ]),
        migrations.CreateModel(name='SupportMessage', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('text', models.TextField()),
            ('from_operator', models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('telegram_message_id', models.BigIntegerField(blank=True, null=True, unique=True)),
            ('telegram_update_id', models.BigIntegerField(blank=True, null=True, unique=True)),
            ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='main.supportconversation')),
        ], options={'ordering': ('pk',)}),
    ]
