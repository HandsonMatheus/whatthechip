from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0002_chipfamily_decode_cap_len'),
    ]

    operations = [
        migrations.AddField(
            model_name='chipfamily',
            name='pn_length',
            field=models.IntegerField(
                null=True, blank=True,
                help_text=(
                    "Comprimento canônico do PN (sem sufixo opcional após hífen). "
                    "Ex: KLM8G1GETF = 10. Usado pela UI de PIN para detectar "
                    "conclusão da entrada e disparar o decode automaticamente. "
                    "Deixar em branco se o comprimento for variável."
                ),
            ),
        ),
    ]
