from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('main', '0019_guild_improvements')]
    operations = [migrations.AddIndex(
        model_name='person',
        index=models.Index(fields=['position', 'goal', 'is_active', 'is_public', '-mmr', 'id'],
                           name='player_role_goal_mmr'),
    )]
