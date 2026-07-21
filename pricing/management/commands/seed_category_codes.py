"""
seed_category_codes — F12: numeração INICIAL dos códigos de categoria.

Junta todas as chaves de preço existentes (linhas do grid ``Price`` + chaves
já materializadas no estoque ``InventoryEntry``) e atribui códigos ``C-###``
em **ordem SORTEADA** (uma vez só — se fosse na ordem natural da grade, o
número viraria quase-ordinal e vazaria a estrutura que a máscara esconde).
Depois do seed, categoria nova ganha o próximo sequencial automaticamente
(``CategoryCode.label_for_key``). Idempotente: chave já codificada é pulada.

    python manage.py seed_category_codes             # dry-run
    python manage.py seed_category_codes --commit
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction

from pricing.models import CategoryCode, Price


class Command(BaseCommand):
    help = ('F12: atribui códigos C-### às categorias existentes em ordem '
            'SORTEADA (uma vez). Dry-run por padrão.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **opts):
        from estoque.models import InventoryEntry
        keys = set()
        for r in Price.all_companies.values_list('kind', 'gen', 'tier_value',
                                                 'tier_unit'):
            keys.add(r)
        # all_companies: o código é GLOBAL — cobre chaves de toda empresa.
        for r in (InventoryEntry.all_companies
                  .filter(price_tier_value__isnull=False)
                  .values_list('price_kind', 'price_gen', 'price_tier_value',
                               'price_tier_unit').distinct()):
            keys.add(r)

        existentes = set(CategoryCode.objects.values_list(
            'kind', 'gen', 'tier_value', 'tier_unit'))
        novas = sorted(keys - existentes)          # ordem estável p/ o log…
        random.shuffle(novas)                      # …numeração SORTEADA

        self.stdout.write(f'=== seed_category_codes '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  chaves no sistema: {len(keys)} · já codificadas: '
                          f'{len(existentes)} · novas: {len(novas)}')
        if not novas:
            self.stdout.write(self.style.SUCCESS('Nada a fazer.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado (a ordem sorteada é refeita no '
                'commit). Re-rode com --commit.'))
            return

        from django.db.models import Max
        nxt = (CategoryCode.objects.aggregate(m=Max('code'))['m'] or 0) + 1
        with transaction.atomic():
            for (kind, gen, tier_value, tier_unit) in novas:
                CategoryCode.objects.create(
                    kind=kind, gen=gen, tier_value=tier_value,
                    tier_unit=tier_unit, code=nxt)
                nxt += 1
        self.stdout.write(self.style.SUCCESS(
            f'✅ {len(novas)} categoria(s) codificadas (C-001…C-{nxt - 1:03d}, '
            'ordem sorteada). Ver /admin/pricing/categorycode/.'))
