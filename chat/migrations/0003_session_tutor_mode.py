from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_session_include_memories"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="tutor_mode",
            field=models.BooleanField(default=True),
        ),
    ]
