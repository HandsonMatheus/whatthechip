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

from tenancy.access import role_required

from .models import STATUS_DRAFT, SalesOrder
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
    ctx = {'so': so}
    if so.status == STATUS_DRAFT:
        pairs = services.live_quotes(so)
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
        ctx.update({'lines': so.lines.all(), 'fx_rate': so.fx_usd_rate})
    return render(request, 'vendas/so_detail.html', ctx)


@role_required('admin')
def so_pdf(request, pk):
    """F11.2c — PDF simples da OV (sem timbre; dono, 2026-07-16). Draft sai
    com os valores VIVOS do momento; confirmada, com os congelados."""
    from django.http import HttpResponse
    from .pdf import render_so_pdf     # reportlab só aqui

    so = get_object_or_404(
        SalesOrder.objects.select_related('lot', 'buyer'), pk=pk)
    rows = []
    if so.status == STATUS_DRAFT:
        pairs = services.live_quotes(so)
        total_rmb, total_usd, _pending = services.draft_totals(pairs)
        fx_rate = so.buyer.fx_usd_rate
        for line, q in pairs:
            priced = q.status == 'PRICED'
            rows.append({
                'label': line.label if priced
                         else f'{line.label} — {q.reason}',
                'qty': str(line.quantity),
                'unit_rmb': q.rmb_display if priced else None,
                'total_rmb': str(q.rmb * line.quantity) if priced else None,
                'total_usd': str(q.price_min * line.quantity) if priced else None,
            })
    else:
        total_rmb, total_usd = so.total_rmb or 0, so.total_usd or 0
        fx_rate = so.fx_usd_rate or so.buyer.fx_usd_rate
        for line in so.lines.all():
            priced = line.unit_rmb is not None
            rows.append({
                'label': line.label, 'qty': str(line.quantity),
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
