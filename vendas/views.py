"""
vendas/views.py — menu Vendas.

**Dois andares de permissão (dono, 2026-08-14 — revisa o admin-only da F11.2):**

- **COMERCIAL — gerente para cima** (`so_list`, `so_detail`, `so_pdf`,
  `so_confirm`, `so_cancel`): quem fecha o lote conduz a venda dele. A regra
  "gerente não vê valor" (matriz §8 do PLANO_MULTITENANT) **continua valendo**
  — o gerente opera com ¥/US$/taxa MASCARADOS (`can_see_price`), e a máscara é
  SERVER-SIDE: a view não põe o número no contexto (esconder no template nunca
  é a barreira).
- **FINANCEIRO — admin** (`settlement_new`, `invoice_*`): acerto, fatura e
  pagamento são o RESULTADO que o comprador devolve. Quando existir a tela do
  comprador, migram para lá; até então é o admin quem lança.

O comprador segue segredo de plataforma (F11.3): a contraparte é o rótulo fixo
"WhatTheChip" — nenhuma destas telas estampa o nome/slug real dele.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from tenancy.access import can_see_price, is_unmasked, role_required
from tenancy.ui import ui   # E5: canary por empresa (§17.7)

from .models import (INV_OPEN, Invoice, STATUS_CONFIRMED, STATUS_DRAFT,
                     SalesOrder)
from . import services


def _fx_viva(buyer, so=None):
    """Taxa exibida no RASCUNHO (PLANO_FX Fase C): a TRAVADA do lote, se o
    fechamento já capturou; senão a de mercado vigente. OV confirmada usa a
    congelada dela (so.fx_usd_rate), nunca esta."""
    if so is not None and so.lot_id and so.lot.fx_rate is not None:
        return so.lot.fx_rate
    from pricing.engine import current_fx_rate
    return current_fx_rate(buyer)[0]



def _pode_faturar(request) -> bool:
    """Andar FINANCEIRO (acerto/fatura/pagamento) = admin da empresa. O gerente
    vê a OV mas não emite nem paga — e por isso também não recebe o link."""
    membership = getattr(request, 'membership', None)
    return bool(membership and membership.has_role('admin'))


@role_required('manager')
def so_list(request):
    # list(): a máscara abaixo escreve nas INSTÂNCIAS (nunca no banco) — o
    # número simplesmente não chega ao HTML de quem não pode vê-lo.
    orders = list(SalesOrder.objects.select_related('lot', 'buyer')
                  .order_by('-created_at')[:200])
    ver_valor = can_see_price(request)
    if not ver_valor:
        for o in orders:
            o.total_rmb = o.total_usd = None
    return render(request, ui(request, 'vendas/so_list.html'),
                  {'orders': orders, 'ver_valor': ver_valor})


@role_required('manager')
def so_detail(request, pk):
    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'buyer'), pk=pk)
    # F11.4: smart button FATURA (ativa) + CTA de acerto quando confirmada.
    # Os dois são do andar financeiro → só o admin recebe (link que daria 403
    # não vai pra tela do gerente).
    faturar = _pode_faturar(request)
    invoice = ((Invoice.all_companies.filter(order=so)
                .exclude(status='cancelled').first()) if faturar else None)
    ver_valor = can_see_price(request)
    ctx = {'so': so, 'invoice': invoice, 'ver_valor': ver_valor,
           'can_settle': (faturar and so.status == STATUS_CONFIRMED
                          and invoice is None)}
    unmasked = is_unmasked(request)              # F12: rótulo real × C-###
    if so.status == STATUS_DRAFT:
        pairs = services.live_quotes(so)
        services.annotate_labels([l for l, _q in pairs], unmasked)
        total_rmb, total_usd, pending = services.draft_totals(pairs)
        # Linhas prontas p/ template (aritmética aqui — template não calcula).
        rows = []
        for line, q in pairs:
            priced = q.status == 'PRICED'
            rows.append({
                'line': line, 'priced': priced, 'reason': q.reason,
                # mid = valor exato quando fixo; ponto médio quando faixa.
                'unit_rmb': f'{q.value_rmb().normalize():f}' if priced else None,
                'unit_usd': q.value() if priced else None,
                'total_rmb': (q.value_rmb() * line.quantity) if priced else None,
                'total_usd': (q.value() * line.quantity) if priced else None,
            })
        ctx.update({'rows': rows, 'live_total_rmb': total_rmb,
                    'live_total_usd': total_usd, 'pending': pending,
                    'fx_rate': _fx_viva(so.buyer, so)})
    else:
        ctx.update({'lines': services.annotate_labels(
                        list(so.lines.all()), unmasked),
                    'fx_rate': so.fx_usd_rate})
    if not ver_valor:
        _mascarar_valores(ctx)
    return render(request, ui(request, 'vendas/so_detail.html'), ctx)


def _mascarar_valores(ctx: dict) -> None:
    """Tira do CONTEXTO todo número de dinheiro (dono, 2026-08-14).

    O gerente vê categoria, quantidade e estado da ordem; ¥, US$ e taxa somem
    do HTML — não ficam "escondidos por CSS". A quantidade FICA: é a operação
    dele (o que saiu do lote), não o valor. Mexe só nas instâncias em memória.
    """
    ctx['fx_rate'] = None
    ctx['live_total_rmb'] = ctx['live_total_usd'] = None
    for row in ctx.get('rows') or []:
        row['unit_rmb'] = row['unit_usd'] = None
        row['total_rmb'] = row['total_usd'] = None
    for line in ctx.get('lines') or []:
        # total_rmb/total_usd são @property derivadas do unitário — zerar o
        # unitário zera o total (não há o que atribuir).
        line.unit_rmb = line.unit_usd = None
    so = ctx.get('so')
    if so is not None:
        so.total_rmb = so.total_usd = so.fx_usd_rate = None


@role_required('manager')
def so_pdf(request, pk):
    """PDF do LOTE — **um documento só, em duas versões** (dono, 2026-08-18).

    - **Não vê preço (gerente/operador):** conferência do lote + embarque —
      quantidade por caixa WTC e por tipo/capacidade, quem fechou, quando, o
      câmbio travado e os blocos SHIP FROM / SHIP TO. **Nenhuma coluna de
      dinheiro existe nele**: a barreira é estrutural, não uma máscara.
    - **Vê preço (admin da empresa / plataforma):** o MESMO documento com
      ¥ unitário e totais em ¥/US$ na tabela de categorias — *"a única
      diferença é que tem preços"*.

    O gate é o ``can_see_price`` (fonte única) — nunca "é admin?" aqui. O PDF
    comercial antigo (``render_so_pdf``) saiu do caminho da tela em
    2026-08-18; a função continua no módulo enquanto o dono valida o novo.
    """
    from .pdf import render_so_manager_pdf     # reportlab só aqui

    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'lot__closed_by', 'buyer',
                                          'company'), pk=pk)
    doc = services.manager_document(
        so,
        unmasked=is_unmasked(request),         # F12: rótulo real × C-###
        with_prices=can_see_price(request))
    return _pdf_response(render_so_manager_pdf(doc), so)


def _pdf_response(pdf: bytes, so):
    """Download com o nome canônico da ordem (a '/' do código vira '-')."""
    from django.http import HttpResponse
    resp = HttpResponse(pdf, content_type='application/pdf')
    fname = so.code.replace('/', '-') + '.pdf'
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@role_required('manager')
@require_POST
def so_confirm(request, pk):
    so = get_object_or_404(SalesOrder.objects, pk=pk)
    try:
        # unmasked: a mensagem de pendência lista CATEGORIAS — quem não é
        # plataforma recebe o código C-### (F12), nunca o rótulo real.
        services.confirm(so, request.user, unmasked=is_unmasked(request))
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    else:
        messages.success(request, _('Ordem confirmada — valores congelados '
                                    '(¥ + taxa do contrato + US$).'))
    return redirect('vendas:so_detail', pk=so.pk)


@role_required('manager')
@require_POST
def so_cancel(request, pk):
    so = get_object_or_404(SalesOrder.objects, pk=pk)
    services.cancel(so, request.user)
    messages.success(request, _('Ordem cancelada.'))
    return redirect('vendas:so_detail', pk=so.pk)


# ═══ F11.4 — Acerto → Fatura → Pagamentos ═══════════════════════════════════

@role_required('admin')
def settlement_new(request, pk):
    """Tela do RESULTADO do comprador: linhas da OV confirmada com campos de
    rejeitados/novo ¥; salvar cria Acerto + Fatura num ato (OV intacta)."""
    from decimal import Decimal, InvalidOperation
    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'buyer'), pk=pk)
    lines = list(so.lines.all())
    if request.method == 'POST':
        adjustments = {}
        try:
            for line in lines:
                rej_raw = (request.POST.get(f'rej_{line.pk}') or '').strip()
                novo_raw = (request.POST.get(f'price_{line.pk}') or '').strip()
                rej = int(rej_raw) if rej_raw else 0
                novo = (Decimal(novo_raw.replace(',', '.'))
                        if novo_raw else None)
                if rej or novo is not None:
                    adjustments[line.pk] = (rej, novo)
        except (ValueError, InvalidOperation):
            messages.error(request, _('Valores ilegíveis — use números.'))
            return redirect('vendas:settlement_new', pk=so.pk)
        try:
            _st, inv = services.settle_and_invoice(
                so, adjustments, request.user,
                notes=(request.POST.get('notes') or '').strip())
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('vendas:settlement_new', pk=so.pk)
        messages.success(request, _('Resultado registrado — fatura emitida '
                                    'com o valor final.'))
        return redirect('vendas:invoice_detail', pk=inv.pk)
    services.annotate_labels(lines, is_unmasked(request))     # F12
    return render(request, ui(request, 'vendas/settlement_form.html'),
                  {'so': so, 'lines': lines})


@role_required('admin')
def invoice_detail(request, pk):
    inv = get_object_or_404(
        Invoice.objects.select_related('order__lot', 'settlement'), pk=pk)
    adj = (list(inv.settlement.lines.select_related('order_line'))
           if inv.settlement_id else [])
    services.annotate_labels([a.order_line for a in adj],
                             is_unmasked(request))             # F12
    return render(request, ui(request, 'vendas/invoice_detail.html'), {
        'inv': inv, 'adjustments': adj,
        'payments': inv.payments.select_related('created_by'),
    })


@role_required('admin')
@require_POST
def invoice_pay(request, pk):
    from datetime import date
    from decimal import Decimal, InvalidOperation
    inv = get_object_or_404(Invoice.objects, pk=pk)
    try:
        amount = Decimal((request.POST.get('amount') or '')
                         .strip().replace(',', '.'))
        paid_at = (date.fromisoformat(request.POST.get('paid_at'))
                   if request.POST.get('paid_at') else date.today())
    except (InvalidOperation, ValueError):
        messages.error(request, _('Valores ilegíveis — use números.'))
        return redirect('vendas:invoice_detail', pk=inv.pk)
    try:
        services.register_payment(
            inv, amount, paid_at, request.user,
            reference=(request.POST.get('reference') or '').strip())
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    else:
        messages.success(request, _('Pagamento registrado.'))
    return redirect('vendas:invoice_detail', pk=inv.pk)


@role_required('admin')
@require_POST
def invoice_cancel(request, pk):
    inv = get_object_or_404(Invoice.objects, pk=pk)
    try:
        services.cancel_invoice(inv, request.user)
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    else:
        messages.success(request, _('Fatura cancelada — registre um novo '
                                    'acerto para reemitir.'))
    return redirect('vendas:so_detail', pk=inv.order_id)
