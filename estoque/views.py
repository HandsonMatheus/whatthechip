"""
WhatTheChip — Estoque views (com Lotes)
========================================
GET  /estoque/                           → lista de lotes
POST /estoque/novo/                      → cria novo lote
GET  /estoque/lote/<lot_pk>/             → painel do lote
GET  /estoque/lote/<lot_pk>/preview/     → classifica PN (HTMX)
POST /estoque/lote/<lot_pk>/add/         → adiciona chip
POST /estoque/lote/<lot_pk>/remove/<pk>/ → remove entrada
GET  /estoque/lote/<lot_pk>/export/      → exporta .xlsx
POST /estoque/lote/<lot_pk>/fechar/      → fecha lote
POST /estoque/lote/<lot_pk>/reabrir/     → reabre lote
"""

import io
import json
import re
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chips.engine import classify
from chips.models import UnknownChip

from .models import InventoryEntry, Lot


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalise_pn(raw: str) -> str:
    return re.sub(r'[^A-Z0-9\-]', '', (raw or '').strip().upper())


def _has_capacity(result: dict) -> bool:
    return bool(
        result.get('capacity')
        or result.get('emcp_ram')
        or result.get('emcp_nand')
        or result.get('dram_density')
    )


def _entries_qs(lot, q='', tipo=''):
    qs = InventoryEntry.objects.filter(lot=lot)
    if q:
        qs = qs.filter(part_number__icontains=q)
    if tipo:
        qs = qs.filter(chip_type__icontains=tipo)
    return qs.order_by('-last_updated')


def _get_lot(request, lot_pk):
    return get_object_or_404(Lot, pk=lot_pk, operator=request.user)


# ─── lot list ───────────────────────────────────────────────────────────────

@login_required
def lot_list(request):
    lots = Lot.objects.filter(operator=request.user)
    return render(request, 'estoque/lotes.html', {'lots': lots})


# ─── lot create ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def lot_create(request):
    description = request.POST.get('description', '').strip()
    number = Lot.next_number()
    lot = Lot.objects.create(
        number=number,
        operator=request.user,
        description=description,
    )
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


# ─── lot detail ─────────────────────────────────────────────────────────────

@login_required
def lot_detail(request, lot_pk):
    lot  = _get_lot(request, lot_pk)
    q    = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    entries   = _entries_qs(lot, q, tipo)
    total_qty = sum(e.quantity for e in entries)

    ctx = {
        'lot':       lot,
        'entries':   entries,
        'total_qty': total_qty,
        'q':         q,
        'tipo':      tipo,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'estoque/partials/table_body.html', ctx)

    return render(request, 'estoque/estoque.html', ctx)


# ─── lot close / reopen ──────────────────────────────────────────────────────

@login_required
@require_POST
def lot_close(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    lot.status    = Lot.STATUS_CLOSED
    lot.closed_at = timezone.now()
    lot.save(update_fields=['status', 'closed_at'])
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


@login_required
@require_POST
def lot_reopen(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    lot.status    = Lot.STATUS_OPEN
    lot.closed_at = None
    lot.save(update_fields=['status', 'closed_at'])
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


# ─── preview chip ────────────────────────────────────────────────────────────

@login_required
def preview_chip(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    pn  = _normalise_pn(request.GET.get('pn', ''))

    if len(pn) < 4:
        return HttpResponse('')

    result  = classify(pn)
    has_cap = _has_capacity(result)

    if result.get('is_emcp'):
        parts = [p for p in [result.get('emcp_nand', ''), result.get('emcp_ram', '')] if p]
        display_cap = ' / '.join(parts)
    else:
        display_cap = result.get('capacity') or result.get('dram_density') or ''

    try:
        current_qty = InventoryEntry.objects.get(lot=lot, part_number=pn).quantity
    except InventoryEntry.DoesNotExist:
        current_qty = 0

    ctx = {
        'lot':         lot,
        'pn':          pn,
        'result':      result,
        'has_cap':     has_cap,
        'display_cap': display_cap,
        'result_json': json.dumps({**result, 'pn': pn}),
        'current_qty': current_qty,
    }
    return render(request, 'estoque/partials/confirm_card.html', ctx)


# ─── add chip ────────────────────────────────────────────────────────────────

@login_required
@require_POST
def add_chip(request, lot_pk):
    lot = _get_lot(request, lot_pk)

    if not lot.is_open:
        return HttpResponse(
            '<div class="est-msg est-msg--error" style="padding:12px 16px;border:1px solid #da1e28;color:#da1e28;margin-top:12px;">'
            'Este lote está fechado. Reabra-o para adicionar chips.'
            '</div>'
        )

    pn  = _normalise_pn(request.POST.get('pn', ''))
    qty = max(1, int(request.POST.get('qty') or 1))

    if len(pn) < 4:
        return HttpResponse(
            '<div class="est-msg est-msg--error" style="padding:12px 16px;">PN inválido.</div>'
        )

    has_cap = request.POST.get('has_cap') == 'true'

    if not has_cap:
        UnknownChip.objects.get_or_create(part_number=pn)
        return render(request, 'estoque/partials/unknown_feedback.html', {'pn': pn})

    defaults = {
        'chip_type':             request.POST.get('chip_type', ''),
        'brand':                 request.POST.get('brand', ''),
        'capacity':              request.POST.get('capacity', ''),
        'emcp_ram':              request.POST.get('emcp_ram', ''),
        'emcp_nand':             request.POST.get('emcp_nand', ''),
        'is_emcp':               request.POST.get('is_emcp') == 'true',
        'interface':             request.POST.get('interface', ''),
        'classification_source': request.POST.get('classification_source', ''),
        'quantity':              qty,
    }

    entry, created = InventoryEntry.objects.get_or_create(
        lot=lot, part_number=pn, defaults=defaults,
    )

    if not created:
        InventoryEntry.objects.filter(pk=entry.pk).update(
            quantity=F('quantity') + qty,
            last_updated=timezone.now(),
        )

    entries   = _entries_qs(lot)
    total_qty = sum(e.quantity for e in entries)

    response = render(request, 'estoque/partials/table_body.html', {
        'lot':        lot,
        'entries':    entries,
        'total_qty':  total_qty,
        'just_added': pn,
    })
    response['HX-Trigger'] = json.dumps({'est:added': {'pn': pn, 'qty': qty, 'pk': entry.pk}})
    return response


# ─── remove entry ────────────────────────────────────────────────────────────

@login_required
@require_POST
def remove_entry(request, lot_pk, pk):
    lot   = _get_lot(request, lot_pk)
    entry = get_object_or_404(InventoryEntry, pk=pk, lot=lot)
    qty   = max(1, int(request.POST.get('qty') or 1))

    if qty >= entry.quantity:
        entry.delete()
    else:
        InventoryEntry.objects.filter(pk=entry.pk).update(quantity=F('quantity') - qty)

    entries   = _entries_qs(lot)
    total_qty = sum(e.quantity for e in entries)

    return render(request, 'estoque/partials/table_body.html', {
        'lot':       lot,
        'entries':   entries,
        'total_qty': total_qty,
    })


# ─── export xls ──────────────────────────────────────────────────────────────

@login_required
def export_xls(request, lot_pk):
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    except ImportError:
        return HttpResponse('openpyxl não instalado.', status=500)

    lot     = _get_lot(request, lot_pk)
    entries_list = list(_entries_qs(lot))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Lote {lot.number:03d}'

    header_fill  = PatternFill('solid', fgColor='0F62FE')
    header_font  = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_align = Alignment(horizontal='left', vertical='center')
    cell_border  = Border(bottom=Side(style='thin', color='E0E0E0'))
    mono_font    = Font(name='Courier New', size=10)

    headers    = ['Part Number', 'Brand', 'Type', 'Capacity', 'Interface', 'Qty.', 'Source', 'Last Added']
    col_widths = [22, 16, 12, 20, 16, 8, 18, 20]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w

    ws.row_dimensions[1].height = 28

    for row_idx, entry in enumerate(entries_list, start=2):
        data = [
            entry.part_number,
            entry.brand or '—',
            entry.chip_type or '—',
            entry.display_capacity,
            entry.interface or '—',
            entry.quantity,
            entry.classification_source or '—',
            entry.last_updated.strftime('%d/%m/%Y %H:%M:%S') if entry.last_updated else '—',
        ]
        for col_idx, value in enumerate(data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border    = cell_border
            cell.alignment = Alignment(vertical='center')
            if col_idx == 1:
                cell.font = mono_font
        ws.row_dimensions[row_idx].height = 20

    total_row  = len(entries_list) + 2
    total_font = Font(name='Calibri', bold=True, size=10)
    ws.cell(row=total_row, column=1, value='TOTAL').font = total_font
    ws.cell(row=total_row, column=6, value=sum(e.quantity for e in entries_list)).font = total_font

    wb.properties.creator = 'WhatTheChip?'
    wb.properties.title   = f'Lote #{lot.number:03d} — {request.user.username}'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f'lote_{lot.number:03d}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
