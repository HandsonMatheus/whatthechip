"""
seed_category_codes — v3: carrega a TABELA FUNDADORA da convenção universal.

A convenção (dono, 2026-07-23) vive em ``pricing/convention.py`` — fixa,
global, eterna. Este comando é DETERMINÍSTICO: grava exatamente a tabela
fundadora (zero aleatoriedade — qualquer deploy, em qualquer país, produz os
MESMOS códigos). Idempotente: linha já existente é conferida (chave E número
têm que bater — divergência é ERRO alto, nunca sobrescrita silenciosa).

Categoria nova NÃO nasce aqui: nasce na primeira APROVAÇÃO na bancada
(``CategoryCode.label_for_key`` — próximo número livre da letra) e deve ser
ANEXADA à tabela do ``convention.py`` como registro da convenção.

    python manage.py seed_category_codes                     # dry-run
    python manage.py seed_category_codes --commit
    python manage.py seed_category_codes --reset --commit    # APAGA e recarrega
                                                             # (SÓ pré-deploy)
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.convention import FOUNDING_TABLE, KIND_LETTER
from pricing.models import CategoryCode, Price, fold_gen


class Command(BaseCommand):
    help = ('F12 v3: grava a TABELA FUNDADORA da convenção universal de '
            'caixas (determinística). Dry-run por padrão; --reset recarrega.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--reset', action='store_true',
                            help='Apaga TODOS os códigos antes de carregar '
                                 '(pré-deploy apenas: renumera as caixas).')

    def handle(self, *args, **opts):
        self.stdout.write(f'=== seed_category_codes v3 '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")

        # Higiene do GRID: linha ainda grafada na variante (LPDDR4X/DDR3L…)
        # dobra na base — avisa pro dono fundir/renomear no admin (gêmeas com
        # ¥ divergente são decisão dele; a busca de preço já lê dobrado).
        dobraveis = []
        for kind, gen, tv, tu in Price.all_companies.values_list(
                'kind', 'gen', 'tier_value', 'tier_unit'):
            if fold_gen(kind, gen) != gen:
                dobraveis.append(f'{kind} {gen} {tv}{tu} → {fold_gen(kind, gen)}')
        if dobraveis:
            self.stdout.write(self.style.WARNING(
                '⚠ Linha(s) do grid grafadas na VARIANTE (a leitura de preço '
                'dobra na base; funda/renomeie no admin — se houver gêmea, '
                'decida o ¥):'))
            for d in sorted(dobraveis):
                self.stdout.write(f'    {d}')

        existentes = {(c.kind, c.gen, c.tier_value, c.tier_unit): c
                      for c in CategoryCode.objects.all()}
        if opts['reset']:
            self.stdout.write(self.style.WARNING(
                f'--reset: {len(existentes)} código(s) atuais serão APAGADOS '
                'e a tabela fundadora recarregada. SÓ antes do deploy.'))
            existentes = {}

        novas, conferidas, conflitos = [], 0, []
        for kind, gen, tier, unit, code in FOUNDING_TABLE:
            key = (kind, gen, Decimal(tier).quantize(Decimal('0.1')), unit)
            atual = existentes.get(key)
            if atual is None:
                novas.append((kind, gen, Decimal(tier), unit, code))
            elif atual.code != code:
                conflitos.append(f'{key} → banco={atual.code} '
                                 f'convenção={code}')
            else:
                conferidas += 1
        if conflitos:
            raise CommandError(
                'DIVERGÊNCIA banco × convenção (código NUNCA muda — resolva '
                'antes; --reset se for pré-deploy):\n  ' + '\n  '.join(conflitos))

        self.stdout.write(f'  tabela fundadora: {len(FOUNDING_TABLE)} · '
                          f'já no banco (conferidas): {conferidas} · '
                          f'a criar: {len(novas)}')
        if not novas and not opts['reset']:
            self.stdout.write(self.style.SUCCESS('Nada a fazer.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        with transaction.atomic():
            if opts['reset']:
                CategoryCode.objects.all().delete()
            for kind, gen, tier, unit, code in novas:
                CategoryCode.objects.create(
                    kind=kind, gen=gen, tier_value=tier,
                    tier_unit=unit, code=code)
        letras = ', '.join(sorted({KIND_LETTER[k] for k, *_ in FOUNDING_TABLE}))
        self.stdout.write(self.style.SUCCESS(
            f'✅ Convenção carregada ({len(novas)} nova(s); letras {letras}). '
            'Ver /admin/pricing/categorycode/.'))
