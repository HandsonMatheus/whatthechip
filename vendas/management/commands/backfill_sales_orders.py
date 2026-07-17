"""
backfill_sales_orders — F11.3: TODO o histórico vive no menu Vendas.

Lotes FECHADOS sem OV ativa ganham uma **OV retroativa CONFIRMADA** a partir
do congelamento F8 (``LotPricing``, "vendi com qual tabela"):

- ``total_usd``  = o ``total_mid`` congelado (fiel ao registro da época);
- ``total_rmb``  = total_usd ÷ ``--rate-used`` (a taxa em que aqueles USD
  nasceram — 0.15 para tudo que congelou antes da virada F10; lotes fechados
  DEPOIS da virada já nascem com OV pelo hook e não entram aqui);
- ``fx_usd_rate`` = a taxa da época (idem) — auditoria cambial fiel;
- linhas = agregação por (marca, chave F11.1) com QUANTIDADES; o unitário
  fica VAZIO (retroativa: o congelado F8 é por PN/total, não por categoria —
  documentado nas notas da OV);
- ``confirmed_at`` = a data do congelamento (cronologia fiel).

Dry-run por padrão; ``--commit`` grava. Idempotente (lote com OV ativa é
pulado). Numeração: sequência perpétua ATUAL, em ordem de fechamento.

    python manage.py backfill_sales_orders --company eminer                  # dry-run
    python manage.py backfill_sales_orders --company eminer --commit
    python manage.py backfill_sales_orders --company eminer --rate-used 0.15 --commit
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from estoque.models import Lot
from pricing.models import LotPricing
from tenancy.scope import scope_command_to_company
from vendas.models import (DocSequence, SEQ_SO, STATUS_CANCELLED,
                           STATUS_CONFIRMED, SalesOrder, SalesOrderLine)

_CENT = Decimal('0.01')


class Command(BaseCommand):
    help = ('F11.3: gera OVs retroativas (confirmadas) para lotes FECHADOS '
            'sem OV, a partir dos LotPricing congelados. Dry-run por padrão.')

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório com 2+ ativas).')
        parser.add_argument('--rate-used', default='0.15',
                            help='Taxa em que os USD congelados nasceram '
                                 '(0.15 = pré-virada F10).')
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        try:
            rate = Decimal(opts['rate_used'])
            if rate <= 0:
                raise InvalidOperation
        except InvalidOperation:
            raise CommandError('--rate-used deve ser > 0 (ex.: 0.15).')

        lots = (Lot.objects.filter(status=Lot.STATUS_CLOSED)
                .order_by('closed_at', 'number'))
        plan, sem_congelado = [], []
        for lot in lots:
            if SalesOrder.all_companies.filter(lot=lot).exclude(
                    status=STATUS_CANCELLED).exists():
                continue                     # já tem OV ativa (hook ou rodada anterior)
            lp = (LotPricing.all_companies.filter(lot=lot)
                  .order_by('-created_at').first())
            if lp is None:
                sem_congelado.append(lot)
                continue
            plan.append((lot, lp))

        self.stdout.write(f'=== backfill_sales_orders ÷{rate} '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  lotes fechados sem OV: {len(plan)}'
                          f' · sem congelado (pulados): {len(sem_congelado)}')
        for lot, lp in plan:
            rmb = (lp.total_mid / rate).quantize(_CENT, ROUND_HALF_UP)
            self.stdout.write(f'    {lot.code:<16} US$ {lp.total_mid} → '
                              f'¥ {rmb} (congelado {lp.created_at:%d/%m/%Y})')
        for lot in sem_congelado:
            self.stdout.write(self.style.WARNING(
                f'    ⚠ {lot.code}: fechado SEM LotPricing — sem base p/ '
                'retroativa (reabra/feche ou ignore).'))
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        criadas = 0
        for lot, lp in plan:
            with transaction.atomic():
                so = SalesOrder(
                    lot=lot, buyer=lp.buyer,
                    number=DocSequence.next_number(lot.company, SEQ_SO),
                    status=STATUS_CONFIRMED,
                    fx_usd_rate=rate,
                    total_usd=lp.total_mid,
                    total_rmb=(lp.total_mid / rate).quantize(_CENT,
                                                             ROUND_HALF_UP),
                    unkeyed_units=(lot.entries.filter(
                        price_tier_value__isnull=True)
                        .aggregate(t=Sum('quantity'))['t'] or 0),
                    notes=(f'Retroativa do congelamento F8 (LotPricing '
                           f'#{lp.pk}, {lp.created_at:%d/%m/%Y}); valores no '
                           f'nível do TOTAL — linhas sem unitário.'),
                )
                so.save()
                # confirmed_at fiel à ÉPOCA (auto_now_add não existe aqui;
                # setar após o save inicial preserva o resto do fluxo):
                SalesOrder.all_companies.filter(pk=so.pk).update(
                    confirmed_at=lp.created_at)
                keyed = (lot.entries.filter(price_tier_value__isnull=False)
                         .values('brand', 'price_kind', 'price_gen',
                                 'price_tier_value', 'price_tier_unit')
                         .annotate(qty=Sum('quantity')).order_by())
                for row in keyed:
                    SalesOrderLine.all_companies.create(
                        order=so, brand=row['brand'] or '',
                        kind=row['price_kind'], gen=row['price_gen'],
                        tier_value=row['price_tier_value'],
                        tier_unit=row['price_tier_unit'],
                        quantity=row['qty'])
                criadas += 1
        self.stdout.write(self.style.SUCCESS(
            f'✅ {criadas} OV(s) retroativa(s) criadas (confirmadas, taxa '
            f'{rate} da época).'))
