"""
Migration: adiciona decode_cap_len ao ChipFamily.

Sem mudança de schema no sentido destrutivo — apenas adiciona uma coluna
com default=1, então todos os registros existentes herdam o comportamento
anterior (chave de 1 caractere).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chips', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chipfamily',
            name='decode_cap_len',
            field=models.IntegerField(
                default=1,
                help_text="Nº de chars da chave de capacidade (padrão=1). "
                          "Use 2 para eMCP com pares como 'X1', 'BT', 'GD'",
            ),
        ),
    ]
