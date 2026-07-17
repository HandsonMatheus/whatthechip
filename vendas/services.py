"""
vendas/services.py — a lógica do fluxo Cotação → OV (F11.2, §12.19).

Fonte única das três operações; as views/hooks só chamam daqui:

- ``create_draft_for_lot(lot, user)`` — no FECHAMENTO do lote: agrega as
  entradas por (marca, chave de preço) e cria a cotação draft para o
  comprador ativo ÚNICO (dono, 2026-07-16: sempre Wu Quan; 0 ou 2+ ativos →
  não cria, loga — decisão humana). Nenhum preço é gravado: draft é VIVO.
- ``live_quotes(so)`` — resolve as linhas do draft contra a tabela Price
  VIVA (BuyerPricingContext — zero classify, zero query por linha).
- ``confirm(so, user)`` / ``cancel(so, user)`` — confirmação congela ¥ +
  taxa contratual + US$ linha a linha (auditoria cambial); cancelamento é
  sempre auditado (quem/quando), nunca delete.
"""

import logging

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (DocSequence, SEQ_SO, STATUS_CANCELLED, STATUS_CONFIRMED,
                     STATUS_DRAFT, SalesOrder, SalesOrderLine)

logger = logging.getLogger(__name__)
_CENT = Decimal('0.01')


def create_draft_for_lot(lot, user=None):
    """Cotação draft do lote fechado. Devolve a SalesOrder ou None (sem
    comprador ativo único / lote sem linha com chave). NUNCA levanta — o
    fechamento do lote não pode travar por causa da venda (padrão F8)."""
    try:
        from pricing.models import Buyer
        buyers = list(Buyer.objects.filter(active=True))
        if len(buyers) != 1:
            logger.warning('vendas: lote %s fechado com %d comprador(es) '
                           'ativo(s) — cotação NÃO criada (esperado: 1).',
                           lot.pk, len(buyers))
            return None
        buyer = buyers[0]

        # Já existe cotação/OV não-cancelada? (re-fechar sem reabrir não duplica)
        if SalesOrder.all_companies.filter(lot=lot).exclude(
                status=STATUS_CANCELLED).exists():
            return None

        # Agregação por (marca, chave) — o resumo por categoria do dono; a
        # marca entra porque o comprador cota POR MARCA (grid da F6).
        keyed = (lot.entries.filter(price_tier_value__isnull=False)
                 .values('brand', 'price_kind', 'price_gen',
                         'price_tier_value', 'price_tier_unit')
                 .annotate(qty=Sum('quantity')).order_by())
        unkeyed = (lot.entries.filter(price_tier_value__isnull=True)
                   .aggregate(t=Sum('quantity'))['t'] or 0)

        with transaction.atomic():
            so = SalesOrder(
                lot=lot, buyer=buyer,
                number=DocSequence.next_number(lot.company, SEQ_SO),
                unkeyed_units=unkeyed)
            so.save()
            for row in keyed:
                SalesOrderLine.all_companies.create(
                    order=so, brand=row['brand'] or '',
                    kind=row['price_kind'], gen=row['price_gen'],
                    tier_value=row['price_tier_value'],
                    tier_unit=row['price_tier_unit'],
                    quantity=row['qty'])
        return so
    except Exception:
        logger.exception('vendas: falha ao criar cotação do lote %s', lot.pk)
        return None


def live_quotes(so):
    """[(linha, PriceQuote)] com valores VIVOS (draft) — resolve a chave da
    linha contra a tabela Price atual. Para OV confirmada, use os campos
    congelados da própria linha (unit_rmb/unit_usd)."""
    from pricing.engine import BuyerPricingContext
    ctx = BuyerPricingContext(so.buyer)
    out = []
    for line in so.lines.all():
        q = ctx.price_from_key(line.kind, line.gen, line.tier_value,
                               line.tier_unit, brand_name=line.brand)
        out.append((line, q))
    return out


def draft_totals(pairs):
    """Totais vivos de um draft a partir de live_quotes(): (¥, US$, pendentes).
    Linha sem preço (não cotado/fora da grade/não compro) entra em pendentes."""
    total_rmb = Decimal('0.00')
    total_usd = Decimal('0.00')
    pending = []
    for line, q in pairs:
        if q.status == 'PRICED':
            total_rmb += q.rmb * line.quantity
            total_usd += q.price_min * line.quantity
        else:
            pending.append((line, q))
    return total_rmb, total_usd, pending


def confirm(so, user):
    """Draft → CONFIRMADA: congela ¥ unitário + taxa + US$ linha a linha.
    Exige TODAS as linhas cotadas (pendência = erro listando o que falta —
    força o grid do comprador a ser completado antes de vender)."""
    if so.status != STATUS_DRAFT:
        raise ValidationError('Só cotação draft pode ser confirmada.')
    pairs = live_quotes(so)
    _t_rmb, _t_usd, pending = draft_totals(pairs)
    if pending:
        faltam = '; '.join(f'{l.label} ({q.status})' for l, q in pending[:8])
        raise ValidationError(
            f'{len(pending)} linha(s) sem preço no grid do comprador — '
            f'complete a cotação antes de confirmar: {faltam}')

    rate = so.buyer.fx_usd_rate
    with transaction.atomic():
        total_rmb = Decimal('0.00')
        total_usd = Decimal('0.00')
        for line, q in pairs:
            line.unit_rmb = q.rmb
            line.unit_usd = (q.rmb * rate).quantize(_CENT, ROUND_HALF_UP)
            line.save()
            total_rmb += line.unit_rmb * line.quantity
            # Total US$ = SOMA das linhas congeladas (estilo fatura: quem
            # confere a conta linha a linha tem que chegar no total) — NÃO
            # total_rmb × taxa, que divergiria por arredondamento por linha.
            total_usd += line.unit_usd * line.quantity
        so.fx_usd_rate = rate
        so.total_rmb = total_rmb.quantize(_CENT, ROUND_HALF_UP)
        so.total_usd = total_usd.quantize(_CENT, ROUND_HALF_UP)
        so.status = STATUS_CONFIRMED
        so.confirmed_at = timezone.now()
        so.confirmed_by = user
        so.save()
    return so


def cancel(so, user):
    """Cancela (draft OU confirmada — auditado; é o pré-requisito para
    reabrir um lote com OV confirmada). Nunca delete."""
    if so.status == STATUS_CANCELLED:
        return so
    so.status = STATUS_CANCELLED
    so.cancelled_at = timezone.now()
    so.cancelled_by = user
    so.save()
    return so
