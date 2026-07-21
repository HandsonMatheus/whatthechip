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


def annotate_labels(lines, unmasked: bool):
    """F12 (máscara, dono 2026-07-17): anexa ``display_label`` — plataforma
    vê o rótulo REAL ("Samsung · eMCP LPDDR4X 64GB"); empresa-CLIENTE vê o
    código opaco C-### (mesma tabela global da bancada/export)."""
    if unmasked:
        for l in lines:
            l.display_label = l.label
        return lines
    from pricing.models import CategoryCode
    for l in lines:
        l.display_label = CategoryCode.label_for_key(
            l.kind, l.gen, l.tier_value, l.tier_unit)
    return lines


# ═══ F11.4 — Acerto → Fatura → Pagamentos ═══════════════════════════════════

def settle_and_invoice(so, adjustments, user, notes=''):
    """RESULTADO do comprador → Acerto + Fatura, num ato atômico (padrão
    Odoo: a OV confirmada fica INTACTA; a fatura carrega o valor final).

    ``adjustments`` = {order_line_pk: (qty_rejected, new_unit_rmb|None)} —
    linhas fora do dict ficam sem ajuste (mantêm qty e ¥ da OV). Sem NENHUM
    ajuste = fatura do valor cheio da OV (acerto vazio, registrado mesmo
    assim — auditoria de que o resultado foi "sem diferenças").

    Regras: só OV CONFIRMADA; só UMA fatura ativa por OV (re-acerto exige
    cancelar a fatura anterior — sem pagamentos); rejeitados ≤ quantidade.
    """
    from .models import (Invoice, SEQ_INVOICE, STATUS_CONFIRMED, Settlement,
                         SettlementLine)
    if so.status != STATUS_CONFIRMED:
        raise ValidationError('Acerto/fatura é de OV CONFIRMADA.')
    if Invoice.all_companies.filter(order=so).exclude(
            status='cancelled').exists():
        raise ValidationError('Esta OV já tem fatura ativa — cancele-a '
                              '(sem pagamentos) para re-acertar.')

    lines = list(so.lines.all())
    by_pk = {l.pk: l for l in lines}
    for pk, (rej, _novo) in adjustments.items():
        line = by_pk.get(pk)
        if line is None:
            raise ValidationError(f'Linha {pk} não é desta OV.')
        if rej > line.quantity:
            raise ValidationError(
                f'{line.label}: rejeitadas ({rej}) > quantidade '
                f'({line.quantity}).')

    with transaction.atomic():
        st = Settlement(order=so, created_by=user, notes=notes)
        st.save()
        total_rmb = Decimal('0.00')
        total_usd = Decimal('0.00')
        rate = so.fx_usd_rate
        for line in lines:
            rej, novo = adjustments.get(line.pk, (0, None))
            if rej or novo is not None:
                SettlementLine.all_companies.create(
                    settlement=st, order_line=line,
                    qty_rejected=rej, new_unit_rmb=novo)
            qty = line.quantity - rej
            unit = novo if novo is not None else line.unit_rmb
            unit_usd = (unit * rate).quantize(_CENT, ROUND_HALF_UP)
            total_rmb += unit * qty
            total_usd += unit_usd * qty          # soma por linha (F10, fatura)
        inv = Invoice(
            order=so, settlement=st,
            number=DocSequence.next_number(so.company, SEQ_INVOICE),
            fx_usd_rate=rate,
            total_rmb=total_rmb.quantize(_CENT, ROUND_HALF_UP),
            total_usd=total_usd.quantize(_CENT, ROUND_HALF_UP),
            issued_by=user)
        inv.save()
    return st, inv


def register_payment(invoice, amount_usd, paid_at, user, reference=''):
    """Pagamento em US$ contra a fatura; saldo zero (ou negativo? nunca —
    barra acima do saldo) marca PAGA."""
    from .models import INV_OPEN, INV_PAID, Payment
    if invoice.status != INV_OPEN:
        raise ValidationError('Só fatura EM ABERTO recebe pagamento.')
    if amount_usd <= 0:
        raise ValidationError('Valor do pagamento deve ser positivo.')
    if amount_usd > invoice.balance_usd:
        raise ValidationError(
            f'Pagamento (US$ {amount_usd}) maior que o saldo '
            f'(US$ {invoice.balance_usd}).')
    with transaction.atomic():
        p = Payment(invoice=invoice, amount_usd=amount_usd,
                    paid_at=paid_at, reference=reference, created_by=user)
        p.save()
        if invoice.balance_usd <= 0:
            invoice.status = INV_PAID
            invoice.save()
    return p


def cancel_invoice(invoice, user):
    """Cancela fatura SEM pagamentos (pré-requisito do re-acerto)."""
    from .models import INV_CANCELLED
    if invoice.payments.exists():
        raise ValidationError('Fatura com pagamento não se cancela — '
                              'trate a diferença num novo acerto/registro.')
    invoice.status = INV_CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.save()
    return invoice
