"""
add_price_row — adiciona UMA faixa nova ao GRID UNIFICADO do comprador.

    python manage.py add_price_row --buyer wuquan --company eminer \
        --kind lpddr --gen LPDDR4X --tier 1 --unit GB \
        --made-by "Samsung,SK Hynix,Micron,Nanya"            # DRY-RUN
    ... --commit                                             # grava

É a ferramenta do fluxo "capacidade fora da grade → o dono adiciona a linha"
(PRECIFICACAO §2/§11 — o sistema NUNCA inventa preço; um chip real revelando
uma faixa nova, ex.: LPDDR4X 1GB do H9HCN, entra por aqui). A linha nasce em
TODAS as listas do comprador, respeitando o grid unificado:

    · marcas em --made-by  → "não cotado"   (fabricam; o comprador cota depois)
    · "Outras marcas"      → "não cotado"   (a genérica oferece tudo, sempre)
    · demais marcas        → "não fabricado"

Idempotente (linha existente é pulada). Dry-run por padrão (regra de ouro #1).
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.models import (Buyer, KIND_UNIT, KINDS, Price, PriceList,
                            STATUS_NOT_MADE, STATUS_UNQUOTED, valid_gen)
from tenancy.scope import scope_command_to_company


class Command(BaseCommand):
    help = ('Adiciona uma faixa nova ao grid unificado do comprador '
            '(made-by → não cotado; demais → não fabricado; Outras marcas '
            'sempre não cotado). DRY-RUN por padrão; --commit grava.')

    def add_arguments(self, parser):
        parser.add_argument('--buyer', required=True, help='Slug do comprador.')
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório se houver 2+ ativas).')
        parser.add_argument('--kind', required=True,
                            help='emmc | ufs | emcp | umcp | lpddr | ddr | gddr')
        parser.add_argument('--gen', default='',
                            help='Geração canônica (LPDDR4X, DDR3L, GDDR6…); '
                                 'vazio para eMMC/UFS.')
        parser.add_argument('--tier', required=True,
                            help='Faixa de capacidade (GB de pacote/NAND; Gb de die).')
        parser.add_argument('--unit', required=True, choices=['GB', 'Gb'],
                            help='GB (pacote) ou Gb (die) — case-sensitive.')
        parser.add_argument('--made-by', default='',
                            help='Marcas que FABRICAM o combo, separadas por '
                                 'vírgula (nome exato da lista). As demais '
                                 'entram como "não fabricado".')
        parser.add_argument('--commit', action='store_true',
                            help='Grava de verdade (sem isto: dry-run).')

    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        buyer = Buyer.all_companies.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")

        kind = opts['kind'].strip().lower()
        gen = opts['gen'].strip()
        if kind not in KINDS:
            raise CommandError(f'kind inválido: {kind!r} (use {sorted(KINDS)}).')
        if not valid_gen(kind, gen):
            raise CommandError(
                f'gen {gen!r} não casa o kind {kind!r} (eMMC/UFS = vazio; '
                'eMCP/uMCP/LPDDR = LPDDRx; DDR = DDRx; GDDR = GDDRx).')
        if opts['unit'] != KIND_UNIT[kind]:
            raise CommandError(
                f'{kind} usa {KIND_UNIT[kind]} (pacote em GB, die em Gb).')
        try:
            tier = Decimal(opts['tier'])
            if tier <= 0:
                raise InvalidOperation
        except InvalidOperation:
            raise CommandError(f"tier ilegível: {opts['tier']!r}")

        made_by = {b.strip() for b in opts['made_by'].split(',') if b.strip()}
        lists = list(PriceList.all_companies.filter(buyer=buyer, active=True)
                     .select_related('brand'))
        nomes = {pl.brand.name for pl in lists if pl.brand_id}
        desconhecidas = made_by - nomes
        if desconhecidas:
            raise CommandError(
                f'--made-by cita marca(s) sem lista neste comprador: '
                f'{sorted(desconhecidas)}. Listas existentes: {sorted(nomes)}.')

        rotulo = f'{kind}/{gen or "—"} {tier.normalize():f}{opts["unit"]}'
        self.stdout.write(f'Faixa nova: {rotulo}  ·  fabricam: '
                          f'{sorted(made_by) or "(nenhuma marca)"}')

        plan = []
        for pl in lists:
            existe = Price.all_companies.filter(
                price_list=pl, kind=kind, gen=gen,
                tier_value=tier, tier_unit=opts['unit']).exists()
            nome = pl.brand.name if pl.brand_id else 'Outras marcas'
            if existe:
                self.stdout.write(f'  {nome}: já tem a linha — pulada')
                continue
            status = (STATUS_UNQUOTED
                      if pl.brand_id is None or pl.brand.name in made_by
                      else STATUS_NOT_MADE)
            plan.append((pl, status))
            self.stdout.write(
                f'  {nome}: +1 linha '
                f'({"não cotado" if status == STATUS_UNQUOTED else "não fabricado"})')

        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Revise e re-rode com --commit.'))
            return

        with transaction.atomic():
            for pl, status in plan:
                Price.all_companies.create(
                    price_list=pl, kind=kind, gen=gen, tier_value=tier,
                    tier_unit=opts['unit'], status=status,
                    source='add_price_row (faixa revelada por chip real)')
        self.stdout.write(self.style.SUCCESS(
            f'✅ COMMIT: {len(plan)} linha(s) criada(s) para {rotulo}. O '
            'comprador cota as "não cotado" no /partner/ (com revisão).'))
