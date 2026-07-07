# PREÇO FIXO (decisão do dono, 2026-07-07): o sistema deixa de suportar FAIXA.
#
# 1. Data migration: acha ta as faixas existentes no PONTO MÉDIO (ROUND_HALF_UP,
#    centavos) — eram ~30 linhas herdadas da planilha do Wuquan ("90-110" RMB).
#    Reverso: no-op (o ponto médio não tem como voltar a ser faixa).
# 2. CheckConstraint `price_fixed_only`: cotado ⇒ min == max, no BANCO.
#
# As colunas price_min/price_max FICAM (representação interna): reativar faixa
# um dia = remover a constraint + a regra do clean(), sem migração de dados.

from decimal import ROUND_HALF_UP, Decimal

import django.db.models.functions.comparison  # noqa: F401 (paridade com o autogerado)
from django.db import migrations, models
from django.db.models import F, Q

_CENT = Decimal('0.01')


def flatten_ranges(apps, schema_editor):
    Price = apps.get_model('pricing', 'Price')
    for p in (Price.objects
              .exclude(price_min=None).exclude(price_max=None)
              .exclude(price_min=F('price_max'))):
        mid = ((p.price_min + p.price_max) / 2).quantize(_CENT, ROUND_HALF_UP)
        p.price_min = p.price_max = mid
        p.save(update_fields=['price_min', 'price_max'])


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0004_rls_lotpricing'),
    ]

    operations = [
        migrations.RunPython(flatten_ranges, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='price',
            constraint=models.CheckConstraint(
                condition=~Q(status='quoted') | Q(price_min=F('price_max')),
                name='price_fixed_only'),
        ),
    ]
