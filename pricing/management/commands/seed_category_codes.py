"""
seed_category_codes — F12: numeração INICIAL dos códigos de categoria.

Fonte das chaves (v2, dono 2026-07-21): **SÓ o grid de preços** — linhas de
lista ATIVA de comprador ATIVO com status cotado/não-cotado. A v1 também
varria as chaves materializadas do estoque e cunhou caixa pra categoria
MORTA (DDR1/DDR2, que são descarte); caixa só existe pra categoria que o
sistema de preços NEGOCIA. A geração DOBRA na base (``fold_gen``: DDR3L→DDR3,
LPDDR4X→LPDDR4 — mesma caixa) e o comando AVISA linha do grid ainda grafada
na variante (ela se canoniza sozinha no próximo save do admin/parceiro).

Atribuição em **ordem SORTEADA** (uma vez só — na ordem natural da grade o
número viraria quase-ordinal e vazaria a estrutura que a máscara esconde).
Depois do seed, categoria nova ganha o próximo sequencial automaticamente
(``CategoryCode.label_for_key`` — que só cria se a chave é vendável).
Idempotente: chave já codificada é pulada.

    python manage.py seed_category_codes                     # dry-run
    python manage.py seed_category_codes --commit
    python manage.py seed_category_codes --reset --commit    # APAGA e ressemeia
                                                             # (só ANTES do deploy
                                                             # — código publicado
                                                             # é permanente)
"""

import random

from django.core.management.base import BaseCommand
from django.db import transaction

from pricing.models import (CategoryCode, Price, STATUS_QUOTED,
                            STATUS_UNQUOTED, fold_gen)


class Command(BaseCommand):
    help = ('F12: atribui códigos C-### às categorias VENDÁVEIS do grid em '
            'ordem SORTEADA (uma vez). Dry-run por padrão; --reset ressemeia.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--reset', action='store_true',
                            help='Apaga TODOS os códigos antes de semear '
                                 '(pré-deploy apenas: renumera as caixas).')

    def handle(self, *args, **opts):
        # all_companies: o código é GLOBAL — cobre o grid de toda empresa.
        rows = (Price.all_companies
                .filter(price_list__active=True,
                        price_list__buyer__active=True,
                        status__in=(STATUS_QUOTED, STATUS_UNQUOTED))
                .values_list('kind', 'gen', 'tier_value', 'tier_unit'))
        keys, dobraveis = set(), []
        for kind, gen, tv, tu in rows:
            base = fold_gen(kind, gen)
            if base != gen:
                dobraveis.append(f'{kind} {gen} {tv}{tu} → {base}')
            keys.add((kind, base, tv, tu))

        self.stdout.write(f'=== seed_category_codes '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        if dobraveis:
            self.stdout.write(self.style.WARNING(
                '⚠ Linha(s) do grid grafadas na VARIANTE (dobram na base; '
                'renomeie no admin ou deixe o próximo save canonizar):'))
            for d in sorted(dobraveis):
                self.stdout.write(f'    {d}')

        if opts['reset']:
            self.stdout.write(self.style.WARNING(
                f'--reset: {CategoryCode.objects.count()} código(s) atuais '
                'serão APAGADOS e as caixas renumeradas. Use SÓ antes do '
                'deploy da F12 (código publicado é permanente).'))

        existentes = (set() if opts['reset'] else
                      set(CategoryCode.objects.values_list(
                          'kind', 'gen', 'tier_value', 'tier_unit')))
        novas = sorted(keys - existentes)          # ordem estável p/ o log…
        random.shuffle(novas)                      # …numeração SORTEADA

        self.stdout.write(f'  categorias vendáveis no grid: {len(keys)} · '
                          f'já codificadas: {len(existentes)} · '
                          f'novas: {len(novas)}')
        if not novas:
            self.stdout.write(self.style.SUCCESS('Nada a fazer.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado (a ordem sorteada é refeita no '
                'commit). Re-rode com --commit.'))
            return

        from django.db.models import Max
        # Reset + recriação num ATO SÓ: falha no meio não deixa o dicionário
        # meio-apagado (padrão defensivo da casa pós-incidente ¥ 2026-07-16).
        with transaction.atomic():
            if opts['reset']:
                CategoryCode.objects.all().delete()
            nxt = (CategoryCode.objects.aggregate(m=Max('code'))['m'] or 0) + 1
            for (kind, gen, tier_value, tier_unit) in novas:
                CategoryCode.objects.create(
                    kind=kind, gen=gen, tier_value=tier_value,
                    tier_unit=tier_unit, code=nxt)
                nxt += 1
        self.stdout.write(self.style.SUCCESS(
            f'✅ {len(novas)} categoria(s) codificadas (até C-{nxt - 1:03d}, '
            'ordem sorteada). Ver /admin/pricing/categorycode/.'))
