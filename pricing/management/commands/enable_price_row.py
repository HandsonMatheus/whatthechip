"""
enable_price_row — HABILITA uma faixa existente para uma marca: flip
"não fabricado" → "não cotado" (o comprador cota depois, com moderação).

    python manage.py enable_price_row --buyer wu-quan --brand "SK Hynix" \
        --kind emcp --gen LPDDR3 --tier 8 --unit GB              # DRY-RUN
    ... --commit                                                  # grava

É a ferramenta da FASE 2 do lote 40 (dono, 2026-07-11): o seed marcou como
"não fabricado" combos que a planilha original não tinha — mas chips REAIS
desses combos apareceram no estoque (ex.: SK Hynix eMCP 8+1GB). Habilitar =
reconhecer que a marca fabrica e abrir a célula amarela pro comprador.

Regras:
  · SÓ transiciona not_made → unquoted. Linha cotada/não-compro NÃO é tocada
    (rebaixar cotação é decisão de admin, no Django admin).
  · Já não-cotado = no-op (idempotente).
  · Garante a GENÉRICA junto ("Outras marcas" oferece tudo): se a linha da
    genérica estiver não-fabricado, flipa também.
  · Linha inexistente → erro apontando o add_price_row (faixa fora da grade).

Dry-run por padrão (regra de ouro #1).
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from pricing.models import (Buyer, KIND_UNIT, KINDS, Price, PriceList,
                            STATUS_NOT_MADE, STATUS_QUOTED, STATUS_UNQUOTED,
                            UNIFIED_KINDS, fold_gen)
from tenancy.scope import platform_scope, scope_command_to_company


class Command(BaseCommand):
    help = ('Habilita uma faixa p/ uma marca: "não fabricado" → "não cotado" '
            '(+ garante a genérica). DRY-RUN por padrão; --commit grava.')

    def add_arguments(self, parser):
        parser.add_argument('--buyer', required=True, help='Slug do comprador.')
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório se houver 2+ ativas).')
        parser.add_argument('--brand', required=True,
                            help='Nome EXATO da marca da lista (ex.: "SK Hynix").')
        parser.add_argument('--kind', required=True,
                            help='emmc | ufs | emcp | umcp | lpddr | ddr')
        parser.add_argument('--gen', default='',
                            help='Geração canônica (LPDDR4, DDR3…); vazio p/ eMMC/UFS.')
        parser.add_argument('--tier', required=True,
                            help='Faixa (GB de pacote/NAND; Gb de die).')
        parser.add_argument('--unit', required=True, choices=['GB', 'Gb'],
                            help='GB (pacote) ou Gb (die) — case-sensitive.')
        parser.add_argument('--commit', action='store_true',
                            help='Grava de verdade (sem isto: dry-run).')

    def handle(self, *args, **opts):
        # eMMC é DUAL-origem (2026-08-01: celular unificado × PCB por marca) —
        # flip cego aqui criaria linha sem origem; o caminho é import/admin.
        if opts.get('kind') == 'emmc':
            raise CommandError(
                'eMMC é dual-origem (celular/PCB, 2026-08-01) — ajuste pelo '
                'import_price_sheet_v2 ou pelo admin, não por este comando.')
        scope_command_to_company(opts['company'], self.stdout)
        buyer = Buyer.all_companies.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")

        kind = opts['kind'].strip().lower()
        if kind not in KINDS:
            raise CommandError(f'kind inválido: {kind!r} (use {sorted(KINDS)}).')
        if opts['unit'] != KIND_UNIT[kind]:
            raise CommandError(
                f'{kind} usa {KIND_UNIT[kind]} (pacote em GB, die em Gb).')
        try:
            tier = Decimal(opts['tier'])
            if tier <= 0:
                raise InvalidOperation
        except InvalidOperation:
            raise CommandError(f"tier ilegível: {opts['tier']!r}")
        if opts['kind'].strip().lower() in UNIFIED_KINDS:
            raise CommandError('Kind UNIFICADO (eMCP/uMCP/LPDDR) não tem linha '
                               'por marca desde 2026-07-27 — nada a habilitar.')
        gen = fold_gen(opts['kind'].strip().lower(), opts['gen'].strip())   # grid canônico (2026-07-21)

        pl = (PriceList.all_companies
              .filter(buyer=buyer, active=True, brand__name=opts['brand'])
              .select_related('brand').first())
        if pl is None:
            nomes = sorted(p.brand.name for p in PriceList.all_companies
                           .filter(buyer=buyer, active=True, brand__isnull=False))
            raise CommandError(
                f"Lista da marca {opts['brand']!r} não existe neste comprador. "
                f'Existentes: {nomes}.')
        generic = (PriceList.all_companies
                   .filter(buyer=buyer, active=True, brand__isnull=True).first())

        rotulo = f'{kind}/{gen or "—"} {tier.normalize():f}{opts["unit"]}'
        plan = []
        for nome, lista in ((pl.brand.name, pl),
                            ('Outras marcas', generic)):
            if lista is None:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ {nome}: comprador sem lista genérica — pulada'))
                continue
            row = Price.all_companies.filter(
                price_list=lista, kind=kind, gen=gen,
                tier_value=tier, tier_unit=opts['unit']).first()
            if row is None:
                raise CommandError(
                    f'{nome}: faixa {rotulo} FORA da grade — use add_price_row '
                    '(a linha nasce em todas as listas de uma vez).')
            if row.status == STATUS_NOT_MADE:
                plan.append((nome, row))
                self.stdout.write(f'  {nome}: não fabricado → não cotado')
            elif row.status == STATUS_UNQUOTED:
                self.stdout.write(f'  {nome}: já está "não cotado" — nada a fazer')
            elif row.status == STATUS_QUOTED:
                self.stdout.write(f'  {nome}: já COTADA (¥ {row.price_min}) — intocada')
            else:
                self.stdout.write(f'  {nome}: está "não compro" — intocada '
                                  '(mudar isso é decisão de admin, no Django admin)')

        self.stdout.write(f'Faixa: {rotulo} · marca: {pl.brand.name} · '
                          f'{len(plan)} linha(s) a habilitar')
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Revise e re-rode com --commit.'))
            return

        # Camada B (RLS): a linha de preço é de PLATAFORMA (company IS NULL
        # desde pricing/0021 — o comprador precifica todas as empresas). Com
        # APENAS o app.company_id do scope_command_to_company, a policy
        # tenant_upd casa ZERO linhas e o Django cai no INSERT de fallback do
        # _save_table → "new row violates row-level security policy" (bug de
        # prod 2026-08-17). platform_scope() abre a transação E emite o
        # SET LOCAL app.platform='1' — mesmo escape do RunPython (CLAUDE.md §7).
        with platform_scope():
            for _nome, row in plan:
                row.status = STATUS_UNQUOTED
                row.price_min = row.price_max = None
                row.quote_date = None
                row.save()

        # Confirmação em BANCO (o pecado do RLS é o no-op SILENCIOSO — nunca
        # confiar no "não deu erro"; §7). Relê e exige o status novo.
        pks = [row.pk for _nome, row in plan]
        gravadas = Price.all_companies.filter(
            pk__in=pks, status=STATUS_UNQUOTED).count()
        if gravadas != len(plan):
            raise CommandError(
                f'GRAVAÇÃO INCOMPLETA: {gravadas}/{len(plan)} linha(s) estão '
                f'"não cotado" no banco. Cheiro de RLS/GUC — confira se o '
                f'app.platform chegou na conexão antes de rodar de novo.')
        self.stdout.write(self.style.SUCCESS(
            f'✅ {len(plan)} linha(s) habilitada(s) (confirmado no banco). O '
            'comprador vê a célula amarela no /partner/ na hora (tabela viva; '
            'pghistory audita).'))
