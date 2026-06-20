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

from chips.conventions import canonical_gen
from chips.engine import assess_profitability, classify, is_dead_by_generation
from chips.models import UnknownChip

from .models import InventoryEntry, Lot, PendingEntry, RejectedEntry


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


def _snapshot(result: dict) -> dict:
    """Campos de snapshot da classificação para PendingEntry/RejectedEntry.

    Coage None → '' porque os CharFields são NOT NULL com default ''. O
    classify() devolve None em emcp_ram/emcp_nand para chips que NÃO são eMCP
    (ex.: LPDDR2 avulso), e `.get(chave, '')` não cobre esse caso (a chave
    existe com valor None) — daí o NotNullViolation no insert."""
    return {
        "chip_type":             result.get("chip_type") or "",
        "brand":                 result.get("brand") or "",
        "capacity":              result.get("capacity") or "",
        "emcp_ram":              result.get("emcp_ram") or "",
        "emcp_nand":             result.get("emcp_nand") or "",
        "is_emcp":               bool(result.get("is_emcp")),
        "interface":             result.get("interface") or "",
        "classification_source": result.get("classification_source") or "",
        "confidence":            result.get("confidence") or "",
    }


def _nearest_in_lot(lot, pn: str) -> str:
    """PN já existente no lote mais parecido — provável original de um typo."""
    pool = list(lot.entries.values_list("part_number", flat=True))
    near = get_close_matches(pn, [p for p in pool if p != pn], n=1, cutoff=0.8)
    return near[0] if near else ""


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalise_pn(raw: str) -> str:
    return re.sub(r'[^A-Z0-9\-]', '', (raw or '').strip().upper())


_PLACEHOLDER_MARKERS = ("não mapead", "nao mapead", "consultar datasheet")


def _real_spec(val) -> bool:
    """True só se o valor é uma spec REAL — não um placeholder de gramática
    incompleta (ex.: "Código 'BG' não mapeado — consultar datasheet")."""
    if not val:
        return False
    low = str(val).lower()
    return not any(m in low for m in _PLACEHOLDER_MARKERS)


def _has_capacity(result: dict) -> bool:
    # Considera o chip "identificável" se tiver capacidade REAL em qualquer campo,
    # OU se for um KnownPart confirmado (known_exact=True) com chip_type definido.
    # ⚠ Placeholder de gramática incompleta ("código não mapeado — consultar
    # datasheet") NÃO conta: senão o operador vê um card confiante (ex.: "DDR4"
    # sem specs) e pode encaixotar um chip que na verdade não foi reconhecido.
    # Esses caem no fluxo de "Não identificado" / UnknownChip.
    return bool(
        _real_spec(result.get('capacity'))
        or _real_spec(result.get('emcp_ram'))
        or _real_spec(result.get('emcp_nand'))
        or _real_spec(result.get('dram_density'))
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


# "Gb" = gigabit (≠ "GB" gigabyte). Densidade DRAM por die.
_GBIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*Gb\b')
_CAP_BYTES_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(GB|MB)\b', re.I)  # capacidade em bytes


def _format_cap(text: str) -> str:
    """Capacidade em MB ou GB, preservando a unidade original.
    '512MB' → '512MB'  |  '8GB' → '8GB'  |  'eMMC 5.1 16GB' → '16GB'
    Não converte MB→GB (512MB é 512MB, não 0.5GB).
    Retorna '' se não encontrar nenhuma unidade reconhecida."""
    if not text:
        return ''
    m = _CAP_BYTES_RE.search(text)
    if not m:
        return ''
    val, unit = m.group(1), m.group(2).upper()
    if val.endswith('.0'):
        val = val[:-2]
    return f"{val}{unit}"


def _density_g(result: dict) -> str:
    """Densidade DRAM por die em Gb, para o rótulo da caixa física (2G/4G/8G).
    Em ordem de prioridade:
      1) `dram_density` (campo canônico, já em Gb): '2Gb = …' → '2';
      2) fallback — deriva da `capacity` em bytes. Em DRAM standalone (1 die por
         chip) a capacidade do CHIP é a própria densidade do die:
         256MB→2G, 512MB→4G, 1GB→8G  (bytes ×8 ÷1024 = Gbit). Muitos registros
         CONFIRMADOS guardam a densidade só como bytes em `capacity`, deixando
         `dram_density` vazio — sem este fallback o rótulo perderia o '+2G'.
    Nunca devolve os bytes crus (256MB confunde — a caixa é por densidade).
    Agnóstico de marca: serve a qualquer fabricante, com ou sem dram_density."""
    m = _GBIT_RE.search(result.get('dram_density') or '')
    if m:
        v = m.group(1)
        return v[:-2] if v.endswith('.0') else v
    c = _CAP_BYTES_RE.search(result.get('capacity') or '')
    if c:
        mb = float(c.group(1)) * (1024 if c.group(2).upper() == 'GB' else 1)
        return f"{mb / 128:g}"   # MB → Gbit  (1Gb = 128 MB)
    return ''


def _capacity_g(result: dict) -> str:
    """Capacidade total do PACOTE em GB, p/ o rótulo de caixa de LPDDR (móvel,
    multi-die): '4GB'→'4', '2GB'→'2', '512MB'→'0.5'. LPDDR é triado pela
    capacidade do pacote (não pela densidade do die), porque empilha vários dies —
    tratar a capacidade como densidade de 1 die daria valor absurdo (4GB→32Gbit)."""
    c = _CAP_BYTES_RE.search(result.get('capacity') or '')
    if not c:
        return ''
    gb = float(c.group(1)) * (1 if c.group(2).upper() == 'GB' else 1 / 1024)
    return f"{gb:g}"


def _compute_destination(result: dict) -> tuple:
    """
    Return (label, category) for the physical storage bin.
    category is used as CSS modifier:
      emcp | umcp | lpddr | ddr | gddr | ufs | emmc | nand | unknown
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

    # GDDR antes do bloco DDR — 'ddr' in 'gddr3' seria True (substring), causando
    # falso-positivo. Samsung usa chip_type dedicado ("GDDR3"/"GDDR5"/etc.);
    # Hynix H5RS usa chip_type="RAM" com subtype="GDDR3" (coberto pelo elif).
    subtype_lower = (result.get('subtype') or '').lower()
    if 'gddr' in ct or ('gddr' in subtype_lower and ct in ('ram', 'dram', 'sdram')):
        gen  = canonical_gen(result.get('subtype') or '', chip_type) or chip_type.upper()
        size = _density_g(result)
        label = f"{gen}+{size}G" if (gen and size) else (gen or 'GDDR')
        return label, 'gddr'

    if 'lpddr' in ct or 'ddr' in ct or ct in ('ram', 'dram', 'sdram'):
        # Caixa de RAM = GERAÇÃO + DENSIDADE, no formato impresso na caixa física,
        # ex.: "DDR3+2G", "DDR4+4G", "LPDDR4+8GB". A geração vem de subtype (ex.: "DDR3",
        # "LPDDR4X") — campo específico para o tipo de RAM. `interface` é a config de
        # barramento (ex.: "x16 @ 800MHz (1600MTPS)") e NÃO é usada como label da caixa.
        # Densidade (Gb) vem de dram_density; capacity (bytes) é ignorada de propósito.
        # canonical_gen (chips/conventions.py, FONTE ÚNICA) reduz o subtype ao
        # token de geração para o label: "LPDDR4 Mobile"→"LPDDR4", "DDR3 SDRAM"→
        # "DDR3", "LPDDR4X Multi-Channel"→"LPDDR4X". Generaliza o antigo strip de
        # "SDRAM" e cobre TODAS as marcas e os dois caminhos (banco e gramática),
        # de forma retroativa, sem reescrever o banco. Fallback p/ interface se o
        # subtype estiver vazio (comportamento anterior preservado).
        gen = canonical_gen(result.get('subtype') or '', chip_type) \
            or (result.get('interface') or '').strip()
        # Tamanho da caixa depende do TIPO (unidade explícita no sufixo):
        #  • LPDDR (móvel) = pacote multi-die → CAPACIDADE do pacote em GB (4GB→"4GB");
        #  • DDR (componente) = 1 die → DENSIDADE do die em Gbit (1GB/die→"8G").
        # "G" sozinho = Gigabits (convenção do setor); "GB" = Gigabytes.
        # UFS/eMMC já usam "GB" explícito; LPDDR alinhado neste padrão.
        if 'lpddr' in ct or gen.upper().startswith('LPDDR'):
            size = _capacity_g(result)
            unit = 'GB'
        else:
            size = _density_g(result)
            unit = 'G'
        if gen and size:
            label = f"{gen}+{size}{unit}"
        elif size:
            label = f"{size}{unit}"
        elif gen:
            label = gen
        else:
            label = 'RAM'
        cat = 'lpddr' if ('lpddr' in ct or gen.upper().startswith('LPDDR')) else 'ddr'
        return label, cat

    if 'nand' in ct:
        # Usa subtype como prefixo do rótulo (ex.: "SLC NAND") + capacidade na
        # unidade original (MB ou GB). _extract_gb só lê GB e perderia "512MB".
        # canonical_gen normaliza a célula: "SLC NAND paralela industrial" → "SLC NAND".
        gen     = canonical_gen(result.get('subtype') or '', chip_type)
        cap_str = _format_cap(result.get('capacity') or '')
        prefix  = gen if gen else 'NAND'
        label   = f"{prefix} {cap_str}" if cap_str else prefix
        return label, 'nand'

    return chip_type or '?', 'unknown'


# ─── gateway de triagem ───────────────────────────────────────────────────────

# Rótulos comerciais da rentabilidade → chave CSS curta (reusados no template).
_PROFIT_KEY = {
    'RENTÁVEL':      'rentavel',
    'NÃO RENTÁVEL':  'nao_rentavel',
    'INDETERMINADO': 'indeterminado',
}


def _compute_gateway(result: dict, has_cap: bool) -> dict:
    """
    Decide o destino de triagem de um chip em 3 etapas de funil (a primeira que
    falha decide), mais um sinal de digitação em paralelo.

    Ordem (importa!): identificação → fonte → rentabilidade.
      1. Identificação: tem specs reais (has_cap)?  Não → 'desconhecido'.
      2. Fonte: confirmado no banco (_is_confirmed)? Não → 'fila' (gestor revisa).
      3. Rentabilidade: assess_profitability. 'NÃO RENTÁVEL' → 'reprovado';
         'RENTÁVEL' ou 'INDETERMINADO' → 'aprovado'.

    Regra de negócio: INDETERMINADO conta como aprovado — melhor deixar entrar do
    que descartar material valioso por falta de regra (ver brainstorm/CLAUDE).

    O typo (fuzzy_suggestions) NÃO é uma etapa: é uma rede de segurança exibida à
    parte, válida em qualquer destino.

    Retorna dict com:
      destination   : 'aprovado' | 'fila' | 'desconhecido' | 'reprovado'
      steps         : 3 dicts {id, label, status: pass|fail|skip, detail}
      typo          : {has: bool, suggestions: list}
      profitable    : string crua de assess_profitability ('' quando não avaliada)
      profitable_key: chave CSS ('rentavel' | 'nao_rentavel' | 'indeterminado')
    """
    fuzzy = result.get('fuzzy_suggestions') or []
    typo = {'has': bool(fuzzy), 'suggestions': fuzzy}
    steps = [
        {'id': 'identificacao', 'label': 'Reconheci',  'status': 'skip', 'detail': ''},
        {'id': 'fonte',         'label': 'Confirmado',  'status': 'skip', 'detail': ''},
        {'id': 'rentabilidade', 'label': 'Rentável',    'status': 'skip', 'detail': ''},
    ]

    def _out(destination, profitable='', by_generation=False):
        return {
            'destination':          destination,
            'steps':                steps,
            'typo':                 typo,
            'profitable':           profitable,
            'profitable_key':       _PROFIT_KEY.get(profitable, 'indeterminado'),
            'reject_by_generation': by_generation,
        }

    # ── Atalho: morto por GERAÇÃO → reprovado direto ─────────────────────────
    # Tecnologia velha (LPDDR2-, DDR2-, MCP legado) é sucata por fato de mercado.
    # Vale mesmo SEM confirmação no banco e SEM capacidade mapeada — a geração é
    # lida da gramática curada. Só geração; nunca capacidade (limite de negócio).
    if is_dead_by_generation(result) and not _is_confirmed(result):
        steps[0].update(status='pass', detail='tipo/geração')
        steps[1].update(status='fail',
                        detail=result.get('classification_source') or 'gramática')
        steps[2].update(status='fail', detail='Geração não rentável')
        return _out('reprovado', 'NÃO RENTÁVEL', by_generation=True)

    # ── 1. Identificação (specs reais) ───────────────────────────────────────
    if not has_cap:
        steps[0].update(status='fail', detail='specs ausentes')
        return _out('desconhecido')
    steps[0].update(status='pass', detail='specs reais')

    # ── 2. Fonte (confirmado no banco) — NÃO altera _is_confirmed ─────────────
    if not _is_confirmed(result):
        steps[1].update(status='fail',
                        detail=result.get('classification_source') or 'gramática')
        return _out('fila')
    steps[1].update(status='pass', detail='banco de dados')

    # ── 3. Rentabilidade (conservador: INDETERMINADO → aprovado) ─────────────
    profitable = assess_profitability(result)
    if profitable == 'NÃO RENTÁVEL':
        steps[2].update(status='fail', detail='Não rentável')
        return _out('reprovado', profitable)

    steps[2].update(
        status='pass',
        detail='Rentável' if profitable == 'RENTÁVEL' else 'Indeterminado (aprovado)',
    )
    return _out('aprovado', profitable)


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

    destination, dest_cat = _compute_destination(result)

    # display_cap = detalhe da sub-linha. Para DRAM, a densidade já está no rótulo
    # da caixa (2G/4G/8G); não mostrar a capacidade em bytes (256MB), que confunde
    # o operador — a caixa de RAM é por densidade.
    if result.get('is_emcp'):
        parts = [p for p in [result.get('emcp_nand', ''), result.get('emcp_ram', '')] if p]
        display_cap = ' / '.join(parts)
    elif dest_cat == 'lpddr':
        # Geração + densidade já estão no rótulo da caixa (ex.: D3+2G). A sub-linha
        # fica só com a marca — sem capacidade em bytes (256MB), que confunde.
        display_cap = ''
    else:
        display_cap = result.get('capacity') or result.get('dram_density') or ''

    try:
        current_qty = InventoryEntry.objects.get(lot=lot, part_number=pn).quantity
    except InventoryEntry.DoesNotExist:
        current_qty = 0

    # Gateway de triagem (3 etapas + typo). Substitui o cálculo solto de
    # profitable/prof_key — a regra de destino agora mora num lugar só.
    gateway = _compute_gateway(result, has_cap)

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
        'gateway':         gateway,
        'gateway_dest':    gateway['destination'],
        'gateway_steps':   gateway['steps'],
        'profitable':      gateway['profitable'],
        'profitable_key':  gateway['profitable_key'],
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

    # Reclassifica no servidor (não confia no hidden do form).
    server_result = classify(pn)
    confirmed = _is_confirmed(server_result)

    # ── Atalho: morto por GERAÇÃO (não confirmado) → descarte direto ─────────
    # Tecnologia velha (LPDDR2-, DDR2-, MCP legado) é sucata por fato de mercado.
    # Reprovado mesmo SEM confirmação e SEM capacidade mapeada — por isso vem
    # ANTES do ramo has_cap (senão um chip sem capacidade cairia em "desconhecido")
    # e da fila. Razão distinta ("geração") para a auditoria separar do reprovado
    # confirmado. Confirmados seguem o fluxo normal abaixo.
    if is_dead_by_generation(server_result) and not confirmed:
        RejectedEntry.objects.create(
            lot=lot, part_number=pn, quantity=qty,
            **_snapshot(server_result),
            rejection_reason='NÃO RENTÁVEL (geração)',
            operator=request.user,
        )
        return render(request, 'estoque/partials/rejected_feedback.html', {
            'pn': pn, 'qty': qty,
            'chip_type': server_result.get('chip_type', ''),
            'capacity':  server_result.get('capacity', ''),
            'by_generation': True,
        })

    has_cap = request.POST.get('has_cap') == 'true'

    if not has_cap:
        UnknownChip.objects.get_or_create(part_number=pn)
        return render(request, 'estoque/partials/unknown_feedback.html', {'pn': pn})

    # ── Bloqueio "só confirmados" ────────────────────────────────────────────
    # Se o PN não é confirmado no banco, NÃO entra no estoque: vai para a fila de
    # conferência (PendingEntry) para o gestor aprovar/reprovar.
    if not confirmed:
        near = _nearest_in_lot(lot, pn)
        pend, p_created = PendingEntry.objects.get_or_create(
            lot=lot, part_number=pn,
            defaults={
                'quantity':          qty,
                **_snapshot(server_result),
                'nearest_confirmed': near,
                'operator':          request.user,
            },
        )
        if not p_created:
            PendingEntry.objects.filter(pk=pend.pk).update(quantity=F('quantity') + qty)
            pend.refresh_from_db()
        return render(request, 'estoque/partials/pending_feedback.html', {
            'pn': pn, 'qty': pend.quantity, 'near': near,
        })

    # ── Bloqueio DURO de rentabilidade ───────────────────────────────────────
    # Chip confirmado e com specs, mas NÃO RENTÁVEL: não entra no estoque. É
    # desviado para RejectedEntry (log de auditoria) e segue para resíduo
    # eletrônico. Decisão de negócio: bloqueio real no servidor, não só na UI.
    # INDETERMINADO/RENTÁVEL passam (regra conservadora — só barra o que é
    # claramente não-rentável).
    if assess_profitability(server_result) == 'NÃO RENTÁVEL':
        RejectedEntry.objects.create(
            lot=lot, part_number=pn, quantity=qty,
            **_snapshot(server_result),
            rejection_reason='NÃO RENTÁVEL',
            operator=request.user,
        )
        return render(request, 'estoque/partials/rejected_feedback.html', {
            'pn': pn, 'qty': qty,
            'chip_type': server_result.get('chip_type', ''),
            'capacity':  server_result.get('capacity', ''),
            'by_generation': False,
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
