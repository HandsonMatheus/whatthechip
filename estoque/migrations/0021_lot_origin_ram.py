# -*- coding: utf-8 -*-
"""Terceira origem de lote: `ram` (módulo de memória) — 2026-08-24.

ADITIVA e segura: só amplia o vocabulário da `CheckConstraint lot_origin_vocab`
de ('phone','pcb') para ('phone','pcb','ram') e atualiza os `choices` (que no
Postgres não geram DDL — é metadado do Django). **Nenhuma linha existente muda**,
nenhum default é criado: a origem continua obrigatória e sem default de
propósito (acordo com o comprador, 2026-08-01).

⚠ A nova origem NÃO é chave de preço. O `pricing/engine.py::_row_origin` só usa
origem no **eMMC** (celular × PCB) e manda qualquer outro valor para o fallback
conservador 'phone'. Um eMMC dentro de um lote `ram` é cotado como celular — de
propósito, e é o mesmo comportamento de material sem origem declarada.

`max_length` continua 5: 'ram' cabe (o maior é 'phone').
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estoque", "0020_lot_code_str"),
        ("tenancy", "0010_alter_company_code_alter_companyevent_code"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="lot",
            name="lot_origin_vocab",
        ),
        migrations.AlterField(
            model_name="lot",
            name="origin",
            field=models.CharField(
                choices=[
                    ("phone", "Celular"),
                    ("pcb", "PCB"),
                    ("ram", "Módulo de memória"),
                ],
                help_text="Classe de placa de onde os chips saíram (celular × PCB) — define a tabela de preço do eMMC.",
                max_length=5,
                verbose_name="Origem",
            ),
        ),
        migrations.AlterField(
            model_name="lotevent",
            name="origin",
            field=models.CharField(
                choices=[
                    ("phone", "Celular"),
                    ("pcb", "PCB"),
                    ("ram", "Módulo de memória"),
                ],
                help_text="Classe de placa de onde os chips saíram (celular × PCB) — define a tabela de preço do eMMC.",
                max_length=5,
                verbose_name="Origem",
            ),
        ),
        migrations.AddConstraint(
            model_name="lot",
            constraint=models.CheckConstraint(
                condition=models.Q(("origin__in", ["phone", "pcb", "ram"])),
                name="lot_origin_vocab",
            ),
        ),
    ]
