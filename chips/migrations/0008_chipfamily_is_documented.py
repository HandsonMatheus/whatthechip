from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0007_chipsubmission'),
    ]

    operations = [
        migrations.AddField(
            model_name='chipfamily',
            name='is_documented',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'False para famílias identificadas mas sem documentação pública verificável. '
                    'Exibe banner de contribuição na UI e desativa persistência automática na fila.'
                ),
            ),
        ),
    ]
