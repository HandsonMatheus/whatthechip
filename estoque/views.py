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
from difflib import get_close_matches

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chips.engine import assess_profitability, classify
from chips.models import UnknownChip

from .models import InventoryEntry, Lot, PendingEntry


# Bloqueio "só confirmados": só passa para o estoque quem é confirmado no banco.
CONFIRMED_SOURCES = {"banco de dados"}
CONFIRMED_CONF = {"confirmed", "manual"}


def _is_confirmed(result: dict) -> bool:
    """True se o PN é confirmado no banco (vence a gramática). Reavaliado no
    servidor — nunca confia no campo hidden do formulário."""
    return (
        result.get("classification_source") in CONFIRMED_SOURCES
        or result.get("confidence") in CONFIRMED_CONF
    )


def _nearest_in_lot(lot, pn: str) -> str:
    """PN já existente no lote mais parecido — provável original de um typo."""
    pool = list(lot.entries.values_list("part_number", flat=True))
    near = get_close_matches(pn, [p for p in pool if p != pn], n=1, cutoff=0.8)
    return near[0] if near else ""


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalise_pn(raw: str) -> str:
    return re.sub(r'[^A-Z0-9\-]', '', (raw or '').strip().upper())


def _has_capacity(result: dict) -> bool:
    # Considera o chip "identificável" se tiver capacidade explícita em qualquer campo
    # OU se for um KnownPart confirmado (known_exact=True) com chip_type definido.
    # Isso evita que chips identificados mas sem capacidade mapeada (ex: DRAM raro,
    # RAM standalone) caiam no fluxo de UnknownChip — o chip É conhecido, apenas
    # a sua densidade não foi catalogada ainda.
    return bool(
        result.get('capacity')
        or result.get('emcp_ram')
        or result.get('emcp_nand')
        or result.get('dram_density')
        or (result.get('known_exact') and result.get('chip_type'))
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


def _extract_gb(text: str) -> str:
    """
    Extrai o valor em GB de uma string de capacidade.
    '8GB' → '8'  |  '1.5GB' → '1.5'  |  'eMMC 5.1 16GB' → '16'
    Usa look-behind negativo para não capturar o ".1" de "eMMC 5.1 8GB".
    """
    if not text:
        return ''
    # Captura número decimal ou inteiro seguido de GB,
    # mas exige que não seja precedido por outro dígito (evita pegar "5.1" de "eMMC 5.1")
    m = re.search(r'(?<!\d)(\d+(?:\.\d+)?)\s*GB', text, re.IGNORECASE)
    if not m:
        return ''
    val = m.group(1)
    # Remove ".0" redundante: "8.0" → "8"
    if val.endswith('.0'):
        val = val[:-2]
    return val


def _compute_destination(result: dict) -> tuple:
    """
    Return (label, category) for the physical storage bin.
    category is used as CSS modifier:
      emcp | umcp | lpddr | ufs | emmc | nand | unknown
    """
    chip_type = (result.get('chip_type') or '').strip()
    ct = chip_type.lower()

    if 'umcp' in ct:
        nand  = _extract_gb(result.get('emcp_nand', ''))
        ram   = _extract_gb(result.get('emcp_ram', ''))
        label = f"UMCP{nand}+{ram}" if nand else 'uMCP'
        return label, 'umcp'

    if 'emcp' in ct or result.get('is_emcp'):
        nand  = _extract_gb(result.get('emcp_nand', ''))
        ram   = _extract_gb(result.get('emcp_ram', ''))
        label = f"EMCP{nand}+{ram}" if nand else 'eMCP'
        return label, 'emcp'

    if 'ufs' in ct:
        cap   = _extract_gb(result.get('capacity', ''))
        label = f"UFS{cap}GB" if cap else 'UFS'
        return label, 'ufs'

    if 'emmc' in ct:
        cap   = _extract_gb(result.get('capacity', ''))
        label = f"EMMC{cap}GB" if cap else 'eMMC'
        return label, 'emmc'

    if 'lpddr' in ct or 'ddr' in ct or ct in ('ram', 'dram', 'sdram'):
        iface = (result.get('interface') or '').upper()
        cap   = _extract_gb(
            result.get('capacity', '') or result.get('dram_density', '')
        )
        if iface and cap:
            label = f"{iface}+{cap}GB"
        elif iface:
            label = iface
        elif cap:
            label = f"RAM {cap}GB"
        else:
            label = 'RAM'
        return label, 'lpddr'

    if 'nand' in ct:
        cap   = _extract_gb(result.get('capacity', ''))
        label = f"NAND {cap}GB" if cap else 'NAND'
        return label, 'nand'

    return chip_type or '?', 'unknown'


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

    destination, dest_cat = _compute_destination(result)

    profitable = assess_profitability(result) if has_cap else 'INDETERMINADO'
    prof_key = {
        'RENTÁVEL':      'rentavel',
        'NÃO RENTÁVEL':  'nao_rentavel',
        'INDETERMINADO': 'indeterminado',
    }.get(profitable, 'indeterminado')

    ctx = {
        'lot':             lot,
        'pn':              pn,
        'result':          result,
        'has_cap':         has_cap,
        'display_cap':     display_cap,
        'result_json':     json.dumps({**result, 'pn': pn}),
        'current_qty':     current_qty,
        'destination':     destination,
        'destination_cat': dest_cat,
        'profitable':      profitable,
        'profitable_key':  prof_key,
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

    # ── Bloqueio "só confirmados" ────────────────────────────────────────────
    # Reclassifica no servidor (não confia no hidden do form). Se o PN não é
    # confirmado no banco, NÃO entra no estoque: vai para a fila de conferência
    # (PendingEntry) para o gestor aprovar/reprovar. Evita typos e chips ainda
    # não catalogados contaminarem o inventário.
    server_result = classify(pn)
    if not _is_confirmed(server_result):
        near = _nearest_in_lot(lot, pn)
        pend, p_created = PendingEntry.objects.get_or_create(
            lot=lot, part_number=pn,
            defaults={
                'quantity':              qty,
                'chip_type':             server_result.get('chip_type', ''),
                'brand':                 server_result.get('brand', ''),
                'capacity':              server_result.get('capacity', ''),
                'emcp_ram':              server_result.get('emcp_ram', ''),
                'emcp_nand':             server_result.get('emcp_nand', ''),
                'is_emcp':               bool(server_result.get('is_emcp')),
                'interface':             server_result.get('interface', ''),
                'classification_source': server_result.get('classification_source', ''),
                'confidence':            server_result.get('confidence', ''),
                'nearest_confirmed':     near,
                'operator':              request.user,
            },
        )
        if not p_created:
            PendingEntry.objects.filter(pk=pend.pk).update(quantity=F('quantity') + qty)
            pend.refresh_from_db()
        return render(request, 'estoque/partials/pending_feedback.html', {
            'pn': pn, 'qty': pend.quantity, 'near': near,
        })

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
