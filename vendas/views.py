"""
vendas/views.py — menu Vendas (F11.2). SÓ ADMIN da empresa: a regra "gerente
não vê valor" (matriz §8 do PLANO_MULTITENANT) vale em toda superfície; o
comprador é segredo de plataforma (F11.3 formaliza o codinome — aqui as telas
já não estampam o nome dele em lugar visível a não-admin porque não há tela
não-admin).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from tenancy.access import is_unmasked, role_required

from .models import (INV_OPEN, Invoice, STATUS_CONFIRMED, STATUS_DRAFT,
                     SalesOrder)
from . import services


@role_required('admin')
def so_list(request):
    orders = (SalesOrder.objects.select_related('lot', 'buyer')
              .order_by('-created_at')[:200])
    return render(request, 'vendas/so_list.html', {'orders': orders})


@role_required('admin')
def so_detail(request, pk):
    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'buyer'), pk=pk)
    # F11.4: smart button FATURA (ativa) + CTA de acerto quando confirmada.
    invoice = (Invoice.all_companies.filter(order=so)
               .exclude(status='cancelled').first())
    ctx = {'so': so, 'invoice': invoice,
           'can_settle': so.status == STATUS_CONFIRMED and invoice is None}
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
                'unit_rmb': q.rmb_display if priced else None,
                'total_rmb': (q.rmb * line.quantity) if priced else None,
                'total_usd': (q.price_min * line.quantity) if priced else None,
            })
        ctx.update({'rows': rows, 'live_total_rmb': total_rmb,
                    'live_total_usd': total_usd, 'pending': pending,
                    'fx_rate': so.buyer.fx_usd_rate})
    else:
        ctx.update({'lines': services.annotate_labels(
                        list(so.lines.all()), unmasked),
                    'fx_rate': so.fx_usd_rate})
    return render(request, 'vendas/so_detail.html', ctx)


@role_required('admin')
def so_pdf(request, pk):
    """F11.2c — PDF simples da OV (sem timbre; dono, 2026-07-16). Draft sai
    com os valores VIVOS do momento; confirmada, com os congelados."""
    from django.http import HttpResponse
    from .pdf import render_so_pdf     # reportlab só aqui

    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'buyer'), pk=pk)
    unmasked = is_unmasked(request)              # F12: rótulo real × C-###
    rows = []
    if so.status == STATUS_DRAFT:
        pairs = services.live_quotes(so)
        services.annotate_labels([l for l, _q in pairs], unmasked)
        total_rmb, total_usd, _pending = services.draft_totals(pairs)
        fx_rate = so.buyer.fx_usd_rate
        for line, q in pairs:
            priced = q.status == 'PRICED'
            rows.append({
                'label': line.display_label if priced
                         else f'{line.display_label} — {q.reason}',
                'qty': str(line.quantity),
                'unit_rmb': q.rmb_display if priced else None,
                'total_rmb': str(q.rmb * line.quantity) if priced else None,
                'total_usd': str(q.price_min * line.quantity) if priced else None,
            })
    else:
        total_rmb, total_usd = so.total_rmb or 0, so.total_usd or 0
        fx_rate = so.fx_usd_rate or so.buyer.fx_usd_rate
        for line in services.annotate_labels(list(so.lines.all()),
                                             unmasked):
            priced = line.unit_rmb is not None
            rows.append({
                'label': line.display_label, 'qty': str(line.quantity),
                'unit_rmb': str(line.unit_rmb) if priced else None,
                'total_rmb': str(line.total_rmb) if priced else None,
                'total_usd': str(line.total_usd) if priced else None,
            })

    pdf = render_so_pdf(so, rows, total_rmb, total_usd, fx_rate)
    resp = HttpResponse(pdf, content_type='application/pdf')
    fname = so.code.replace('/', '-') + '.pdf'
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@role_required('admin')
@require_POST
def so_confirm(request, pk):
    so = get_object_or_404(SalesOrder.objects, pk=pk)
    try:
        services.confirm(so, request.user)
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    else:
        messages.success(request, _('Ordem confirmada — valores congelados '
                                    '(¥ + taxa do contrato + US$).'))
    return redirect('vendas:so_detail', pk=so.pk)


@role_required('admin')
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
    return render(request, 'vendas/settlement_form.html',
                  {'so': so, 'lines': lines})


@role_required('admin')
def invoice_detail(request, pk):
    inv = get_object_or_404(
        Invoice.objects.select_related('order__lot', 'settlement'), pk=pk)
    adj = (list(inv.settlement.lines.select_related('order_line'))
           if inv.settlement_id else [])
    services.annotate_labels([a.order_line for a in adj],
                             is_unmasked(request))             # F12
    return render(request, 'vendas/invoice_detail.html', {
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
