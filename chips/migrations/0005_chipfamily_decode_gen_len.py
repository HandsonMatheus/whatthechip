"""
Migration: adiciona decode_gen_len ao ChipFamily.

Paralelo ao decode_cap_len (0002). Necessário para famílias SK Hynix eMCP
(H9TQ, H9TP) cujas chaves do mapa de RAM têm 2 chars ("AC", "AD", "A8"…).

default=1 preserva comportamento anterior de todas as famílias Samsung
(Samsung usa chaves de 1 char no decode_gen_map — ex: "R"=LPDDR4/4X).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0004_correctionrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='chipfamily',
            name='decode_gen_len',
            field=models.IntegerField(
                default=1,
                help_text="Nº de chars da chave no mapa de geração/RAM (padrão=1). "
                          "Use 2 para eMCP com chaves de 2 chars como 'AC', 'AD', 'A8'.",
            ),
        ),
    ]
