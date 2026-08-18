# F12 — aposentadoria de código de caixa (dono, 2026-08-18).
#
# ADITIVA e NULLABLE de propósito: nada é apagado, nada é reescrito. O código
# aposentado continua no mapa chave→número (o número é ETERNO — apagar faria
# o próximo número livre renascer num código que pode estar etiquetado numa
# caixa física). A aposentadoria em si NÃO acontece aqui: é o comando
# `retire_category_codes --commit`, para o dono ver a lista antes de gravar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0024_buyer_ship_to"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorycode",
            name="retired_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Aposentado em"
            ),
        ),
        migrations.AddField(
            model_name="categorycode",
            name="retired_reason",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
                verbose_name="Motivo da aposentadoria",
            ),
        ),
    ]
