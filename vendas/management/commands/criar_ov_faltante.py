# -*- coding: utf-8 -*-
"""
criar_ov_faltante.py — cria a Ordem de Venda do lote que fechou sem ela.
================================================================================
O conserto do que o `diag_ordem_venda` acha. Chama o MESMO
`create_draft_for_lot` do fechamento — não reimplementa nada, não inventa
número, não congela valor: a OV nasce RASCUNHO com preço vivo, exatamente como
teria nascido na hora certa.

⚠ Não confundir com o `backfill_sales_orders`: aquele é a migração HISTÓRICA
(OV retroativa CONFIRMADA a partir do congelamento F8, com a taxa da época,
sem unitário). Este aqui é para o lote do dia-a-dia que fechou sob o sistema
atual e teve a OV engolida pelo `except` do padrão F8.

Dry-run por padrão. Idempotente: lote com OV viva é pulado.

    python manage.py criar_ov_faltante --company erecyclo             # dry-run
    python manage.py criar_ov_faltante --company erecyclo --lot 1 --commit
    python manage.py criar_ov_faltante --company erecyclo --commit

Se o lote continuar sem OV depois do --commit, a causa NÃO era transitória:
rode o `diag_ordem_venda` — quase sempre é o portão do comprador único.
"""
from django.core.management.base import CommandError

from core.safe_command import SafeWriteCommand
from estoque.models import Lot
from tenancy.models import Company
from tenancy.scope import company_scope, platform_scope
from vendas.models import STATUS_CANCELLED, SalesOrder


class Command(SafeWriteCommand):
    help = ('Cria a Ordem de Venda (rascunho) dos lotes fechados que ficaram '
            'sem ela — pelo mesmo caminho do fechamento.')

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True,
                            help='slug da empresa dona dos lotes')
        parser.add_argument('--lot', default='',
                            help='um lote só (número ou código); vazio = todos')
        parser.add_argument('--commit', action='store_true',
                            help='grava (sem isto é dry-run)')

    def handle(self, *args, **opts):
        from vendas.services import create_draft_for_lot

        try:
            company = Company.objects.get(slug=opts['company'].strip())
        except Company.DoesNotExist:
            raise CommandError(f'Empresa {opts["company"]!r} não existe.')

        alvo = (opts['lot'] or '').strip()
        with platform_scope():
            com_ov = set(SalesOrder.all_companies
                         .exclude(status=STATUS_CANCELLED)
                         .values_list('lot_id', flat=True))
        with company_scope(company):
            fechados = list(Lot.objects.filter(status=Lot.STATUS_CLOSED)
                            .order_by('closed_at', 'number'))
        orfaos = [l for l in fechados if l.pk not in com_ov]
        if alvo:
            orfaos = [l for l in orfaos
                      if str(l.number) == alvo or l.code == alvo]
            if not orfaos:
                self.stdout.write(self.style.SUCCESS(
                    f'Lote {alvo!r}: nada a fazer (não existe, não está '
                    f'fechado, ou já tem OV).'))
                return

        self.stdout.write(f'\n=== criar_ov_faltante — {company.name} '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  {len(fechados)} lote(s) fechado(s) · '
                          f'{len(orfaos)} sem OV')
        if not orfaos:
            self.stdout.write(self.style.SUCCESS('  Nada a fazer. ✓'))
            return
        for l in orfaos:
            self.stdout.write(f'    {l.code}  (fechado '
                              f'{l.closed_at:%d/%m/%Y})' if l.closed_at
                              else f'    {l.code}')
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        # O create_draft_for_lot lê Buyer.objects (escopado) e escreve em
        # tabela com RLS → precisa do escopo da empresa DONA do lote, que fora
        # de request não existe. Mesmo motivo do middleware.
        criadas, falharam = [], []
        for l in orfaos:
            with company_scope(company):
                so = create_draft_for_lot(l)
                # O critério é o BANCO, não o retorno: create_draft_for_lot
                # devolve None tanto no erro quanto no "já existe" (lição do
                # incidente do K9).
                nasceu = SalesOrder.all_companies.filter(lot=l).exclude(
                    status=STATUS_CANCELLED).exists()
            (criadas if nasceu else falharam).append((l, so))

        for l, so in criadas:
            self.stdout.write(self.style.SUCCESS(
                f'  ✅ {l.code} → OV {so.number if so else "(já existia)"}'))
        for l, _so in falharam:
            self.stdout.write(self.style.ERROR(
                f'  ⛔ {l.code} → continua sem OV'))
        self.stdout.write(f'\n{len(criadas)} criada(s) · {len(falharam)} '
                          f'ainda sem OV')
        if falharam:
            self.stdout.write(self.style.ERROR(
                'A causa NÃO é transitória. Rode:\n'
                f'  python manage.py diag_ordem_venda --company '
                f'{company.slug} --lot {falharam[0][0].number}'))
