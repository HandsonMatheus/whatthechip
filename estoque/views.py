"""
WhatTheChip — Estoque views
============================
GET  /estoque/              → painel principal (+ HTMX: filtra tabela)
GET  /estoque/preview/      → HTMX: classifica PN, retorna card de confirmação
POST /estoque/add/          → adiciona/incrementa no estoque (ou registra desconhecido)
POST /estoque/remove/<pk>/  → remove entrada do estoque
"""

import io
import json
import re
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from chips.engine import classify
from chips.models import UnknownChip

from .models import InventoryEntry


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalise_pn(raw: str) -> str:
    """Upper-case, remove tudo que não for alfanumérico ou hífen."""
    return re.sub(r"[^A-Z0-9\-]", "", (raw or "").strip().upper())


def _has_capacity(result: dict) -> bool:
    """Retorna True se o motor conseguiu identificar capacidade."""
    return bool(
        result.get("capacity")
        or result.get("emcp_ram")
        or result.get("emcp_nand")
        or result.get("dram_density")
    )


def _entries_qs(user, q="", tipo=""):
    qs = InventoryEntry.objects.filter(operator=user)
    if q:
        qs = qs.filter(part_number__icontains=q)
    if tipo:
        qs = qs.filter(chip_type__icontains=tipo)
    return qs.order_by("-last_updated")


# ─── views ──────────────────────────────────────────────────────────────────

@login_required
def estoque_view(request):
    """Painel principal. HTMX GET retorna só o corpo da tabela."""
    q    = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()

    entries   = _entries_qs(request.user, q, tipo)
    total_qty = sum(e.quantity for e in entries)

    ctx = {
        "entries":   entries,
        "total_qty": total_qty,
        "q":         q,
        "tipo":      tipo,
    }

    # HTMX retorna só a tabela (busca/filtro)
    if request.headers.get("HX-Request"):
        return render(request, "estoque/partials/table_body.html", ctx)

    return render(request, "estoque/estoque.html", ctx)


@login_required
def preview_chip(request):
    """
    HTMX endpoint: classifica o PN e retorna o card de confirmação.
    Input limpo com < 4 chars → limpa a área.
    """
    pn = _normalise_pn(request.GET.get("pn", ""))

    if len(pn) < 4:
        return HttpResponse("")   # HTMX apaga #confirm-area

    result       = classify(pn)
    has_cap      = _has_capacity(result)

    # Para eMCP, display_capacity agrega RAM + NAND
    display_cap = ""
    if result.get("is_emcp"):
        parts = [p for p in [result.get("emcp_nand", ""), result.get("emcp_ram", "")] if p]
        display_cap = " / ".join(parts)
    else:
        display_cap = result.get("capacity") or result.get("dram_density") or ""

    ctx = {
        "pn":          pn,
        "result":      result,
        "has_cap":     has_cap,
        "display_cap": display_cap,
        "result_json": json.dumps({**result, "pn": pn}),
    }
    return render(request, "estoque/partials/confirm_card.html", ctx)


@login_required
@require_POST
def add_chip(request):
    """
    Adiciona chip ao estoque (incrementa qty se já existe)
    ou registra em UnknownChip se não foi identificado.
    Retorna o corpo da tabela atualizado via HTMX.
    """
    pn  = _normalise_pn(request.POST.get("pn", ""))
    qty = max(1, int(request.POST.get("qty") or 1))

    if len(pn) < 4:
        return HttpResponse(
            '<tr><td colspan="6" class="est-msg est-msg--error">PN inválido (mínimo 4 caracteres).</td></tr>'
        )

    has_cap = request.POST.get("has_cap") == "true"

    if not has_cap:
        # Chip desconhecido → registra na fila e retorna feedback inline
        UnknownChip.objects.get_or_create(part_number=pn)
        return render(request, "estoque/partials/unknown_feedback.html", {"pn": pn})

    # Dados classificados (vêm de inputs hidden no form de confirmação)
    defaults = {
        "chip_type":             request.POST.get("chip_type", ""),
        "brand":                 request.POST.get("brand", ""),
        "capacity":              request.POST.get("capacity", ""),
        "emcp_ram":              request.POST.get("emcp_ram", ""),
        "emcp_nand":             request.POST.get("emcp_nand", ""),
        "is_emcp":               request.POST.get("is_emcp") == "true",
        "interface":             request.POST.get("interface", ""),
        "classification_source": request.POST.get("classification_source", ""),
        "quantity":              qty,
    }

    entry, created = InventoryEntry.objects.get_or_create(
        operator=request.user,
        part_number=pn,
        defaults=defaults,
    )

    if not created:
        # auto_now não dispara via .update() — passamos last_updated explicitamente
        # para que a entrada suba ao topo da tabela (ordenação por -last_updated)
        InventoryEntry.objects.filter(pk=entry.pk).update(
            quantity=F("quantity") + qty,
            last_updated=timezone.now(),
        )

    entries   = _entries_qs(request.user)
    total_qty = sum(e.quantity for e in entries)

    response = render(request, "estoque/partials/table_body.html", {
        "entries":    entries,
        "total_qty":  total_qty,
        "just_added": pn,
    })
    # Dispara evento customizado via HTMX para exibir o toast de confirmação
    response["HX-Trigger"] = json.dumps({
        "est:added": {"pn": pn, "qty": qty, "pk": entry.pk}
    })
    return response


@login_required
def export_xls(request):
    """Exporta o estoque do operador logado para .xlsx (openpyxl)."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        return HttpResponse("openpyxl não instalado. Execute: pip install openpyxl", status=500)

    entries = _entries_qs(request.user)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estoque"

    # ── Estilos Carbon Blue ──────────────────────────────────────
    header_fill = PatternFill("solid", fgColor="0F62FE")
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="left", vertical="center")
    thin = Side(style="thin", color="E0E0E0")
    cell_border = Border(bottom=Side(style="thin", color="E0E0E0"))
    mono_font = Font(name="Courier New", size=10)

    # ── Cabeçalho ─────────────────────────────────────────────────
    headers    = ["Part Number", "Brand", "Type", "Capacity", "Interface", "Qty.", "Source", "Last Added"]
    col_widths = [22, 16, 12, 20, 16, 8, 18, 20]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w

    ws.row_dimensions[1].height = 28

    # ── Dados ────────────────────────────────────────────────────
    for row_idx, entry in enumerate(entries, start=2):
        data = [
            entry.part_number,
            entry.brand or "—",
            entry.chip_type or "—",
            entry.display_capacity,
            entry.interface or "—",
            entry.quantity,
            entry.classification_source or "—",
            entry.last_updated.strftime("%d/%m/%Y %H:%M:%S") if entry.last_updated else "—",
        ]
        for col_idx, value in enumerate(data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = cell_border
            cell.alignment = Alignment(vertical="center")
            if col_idx == 1:
                cell.font = mono_font
        ws.row_dimensions[row_idx].height = 20

    # ── Linha de totais ──────────────────────────────────────────
    total_row = len(list(entries)) + 2
    total_font = Font(name="Calibri", bold=True, size=10)
    ws.cell(row=total_row, column=1, value="TOTAL").font = total_font
    qty_total = sum(e.quantity for e in entries)
    cell_total = ws.cell(row=total_row, column=5, value=qty_total)
    cell_total.font = total_font

    # ── Metadados ─────────────────────────────────────────────────
    wb.properties.creator = "WhatTheChip?"
    wb.properties.title   = f"Estoque — {request.user.username}"

    # ── Resposta HTTP ─────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"estoque_{request.user.username}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def remove_entry(request, pk):
    """
    Remove parcial ou total de uma entrada do estoque do operador logado.
    Se qty >= quantity total: deleta a linha.
    Caso contrário, decrementa apenas a quantidade informada.
    """
    entry = get_object_or_404(InventoryEntry, pk=pk, operator=request.user)
    qty   = max(1, int(request.POST.get("qty") or 1))

    if qty >= entry.quantity:
        entry.delete()
    else:
        InventoryEntry.objects.filter(pk=entry.pk).update(quantity=F("quantity") - qty)

    entries   = _entries_qs(request.user)
    total_qty = sum(e.quantity for e in entries)

    return render(request, "estoque/partials/table_body.html", {
        "entries":   entries,
        "total_qty": total_qty,
    })
