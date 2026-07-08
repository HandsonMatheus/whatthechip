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
import logging
import re
from datetime import datetime
from difflib import get_close_matches

from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from tenancy.access import role_required

from chips.conventions import canonical_gen
from chips.chip_types import canonical_chip_type, generation_of, label_kind
from chips.engine import assess_profitability, classify, is_dead_by_generation
from chips.models import UnknownChip, Brand

from .models import InventoryEntry, Lot, PendingEntry, RejectedEntry

logger = logging.getLogger(__name__)


# Elegibilidade de entrada no estoque: passa quem TEM REGISTRO no banco — confidence
# confirmed, manual OU distributor. Decisão do dono (2026-07-08): distribuidor ENTRA;
# gramática PURA (sem registro no banco) JAMAIS entra → vai pra fila.
# ⚠ Isto é ELEGIBILIDADE DE ESTOQUE, não AUTORIDADE sobre a gramática: distribuidor
# continua NÃO vencendo a gramática no engine (chips/engine.py::_CONFIRMED_CONFIDENCE
# segue só confirmed/manual). As specs de um distribuidor vêm da gramática; ter o
# registro só o torna elegível pra bancada.
CONFIRMED_SOURCES = {"banco de dados"}
CONFIRMED_CONF = {"confirmed", "manual", "distributor"}


def _is_confirmed(result: dict) -> bool:
    """True se o PN é ELEGÍVEL PRO ESTOQUE: tem registro no banco (confidence
    confirmed/manual/distributor) OU a classificação veio do banco. Gramática pura
    (sem registro) → False → fila. (O nome '_is_confirmed' é histórico; hoje inclui
    distribuidor por decisão do dono — ver comentário acima.) Reavaliado no servidor —
    nunca confia no campo hidden do formulário."""
    return (
        result.get("classification_source") in CONFIRMED_SOURCES
        or result.get("confidence") in CONFIRMED_CONF
    )


def _size_for_entry(result: dict) -> str:
    """Tamanho a GRAVAR no estoque. `capacity` (bytes) tem prioridade; para DRAM
    standalone (DDR/GDDR) a capacity vem vazia e o tamanho está em `dram_density`
    ('2Gb = 256MB por die') — extraímos os bytes ('256MB') para não perder o dado.
    Antes este tamanho era simplesmente perdido (estoque gravava vazio → 'None').
    (Regex _CAP_BYTES_RE/_GBIT_RE definidos abaixo; resolvidos em tempo de chamada.)"""
    ct = (result.get("chip_type") or "").upper()
    # DRAM discreta de 1 die (DDR/GDDR/SDRAM/RDRAM) → DENSIDADE em Gbit, formato '2G'
    # (mesma convenção da etiqueta da caixa 'DDR3+2G'). _density_g lê de dram_density
    # ou deriva da capacity em bytes — robusto aos dois jeitos de gravar no catálogo.
    if (ct.startswith("DDR") or ct.startswith("GDDR") or ct in ("SDRAM", "RDRAM")) and "LPDDR" not in ct:
        g = _density_g(result)
        return f"{g}G" if g else ""
    # LPDDR/eMMC/UFS (pacote) → CAPACIDADE em bytes (GB). 'None' (string) = lixo de
    # catálogo → trata como vazio; normaliza o espaço ('256 MB'→'256MB').
    cap = (result.get("capacity") or "").strip()
    if cap and cap.lower() != "none":
        return re.sub(r"\s+([KMGT]B)\b", r"\1", cap)
    # fallback raro: tamanho só em dram_density. bytes têm 'B' MAIÚSCULO; 'Gb' é gigaBIT —
    # case-SENSITIVE (sem re.I) p/ não ler 'Gb' como 'GB' (bug clássico 8×).
    dd = result.get("dram_density") or ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([TGM]B)\b", dd)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    g = _GBIT_RE.search(dd)
    if g:
        mb = float(g.group(1)) * 128
        return f"{mb:g}MB" if mb < 1024 else f"{mb / 1024:g}GB"
    return ""


def _clean_interface(result: dict) -> str:
    """`interface` no estoque = bus width (x16) ou versão (eMMC 5.1) — NUNCA a
    geração (essa vive no chip_type/subtype/label). Remove a geração espelhada
    (DDR3, LPDDR4X, GDDR5…) para o campo ficar CONSISTENTE entre os tipos (era a
    origem do 'alguns espelham, outros não'). Não afeta o label da caixa, que usa
    o `result` cru, não este campo gravado."""
    ifc = (result.get("interface") or "").strip()
    if ifc and re.fullmatch(r"(LP)?DDR\d[A-Z]?|GDDR\d", ifc, re.I):
        return ""
    return ifc


def _snapshot(result: dict) -> dict:
    """Snapshot da classificação para InventoryEntry/PendingEntry/RejectedEntry —
    SEMPRE a partir do classify do SERVIDOR (nunca do POST do cliente).

    Coage None → '' porque os CharFields são NOT NULL com default ''. O
    classify() devolve None em emcp_ram/emcp_nand para chips que NÃO são eMCP
    (ex.: LPDDR2 avulso), e `.get(chave, '')` não cobre esse caso (a chave
    existe com valor None) — daí o NotNullViolation no insert.
    `capacity` captura a densidade DRAM via _size_for_entry; `interface` é limpa
    da geração espelhada via _clean_interface."""
    return {
        "chip_type":             result.get("chip_type") or "",
        "brand":                 result.get("brand") or "",
        "capacity":              _size_for_entry(result),
        "emcp_ram":              result.get("emcp_ram") or "",
        "emcp_nand":             result.get("emcp_nand") or "",
        "is_emcp":               bool(result.get("is_emcp")),
        "interface":             _clean_interface(result),
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


def _current_snapshot(pn: str) -> dict:
    """Snapshot ATUAL do servidor para um PN: `_snapshot(classify(pn))` sem o
    campo `confidence`, mais a derivação do rótulo "banco de dados" para um
    confirmado SEM família casada (ex.: Micron JZ###) — igual ao
    `resnapshot_lote`/`refresh_lote._live_source`. Devolve só os campos de
    exibição (chip_type/brand/capacity/emcp_*/is_emcp/interface/Source)."""
    r = classify(pn) or {}
    snap = _snapshot(r)
    snap.pop("confidence", None)
    if not snap["classification_source"] and (
            r.get("confidence") in ("confirmed", "manual") or r.get("known_exact")):
        snap["classification_source"] = "banco de dados"
    return snap


#: Teto de recálculo SÍNCRONO por render do on-read. O caminho que persiste em
#: massa é o `resnapshot_lote`; a tela só reconcilia o que estiver à vista, sem
#: varrer o lote inteiro a cada abertura (problema 4.4 do BRIEFING_ESCALABILIDADE).
_ONREAD_CAP = 150


def _entries_for_display(lot, q='', tipo=''):
    """Entradas do lote prontas para a TELA, com **cálculo na leitura** (on-read):
    as DEFASADAS — `snapshot_catalog_version` menor que `CatalogVersion.current()`,
    i.e. o catálogo melhorou desde que o chip foi lançado — são recalculadas EM
    MEMÓRIA para mostrar o valor ATUAL, **sem gravar** (quem persiste é o
    `resnapshot_lote`). Limita-se a `_ONREAD_CAP` recálculos por render para não
    classificar o lote inteiro de forma síncrona. O que está em dia sai do banco
    sem custo."""
    from chips.models import CatalogVersion
    cur = CatalogVersion.current()
    entries = list(_entries_qs(lot, q, tipo))
    recomputed = 0
    for e in entries:
        if e.snapshot_catalog_version < cur and recomputed < _ONREAD_CAP:
            for k, v in _current_snapshot(e.part_number).items():
                setattr(e, k, v)   # override em memória — NÃO chama e.save()
            recomputed += 1
    return entries


def _get_lot(request, lot_pk):
    """Lote acessível ao usuário. T1 (papéis, §8 do plano): o lote é um ATIVO DA
    EMPRESA — o gerente abre, o operador lança nele — então caiu o filtro
    ``operator=request.user`` (cada um só via os próprios lotes, o que impediria
    o operador de trabalhar num lote aberto pelo gerente). O campo ``operator``
    do Lot vira "quem abriu". T3: este helper passa a ser escopado por empresa
    via CompanyScopedManager (hoje há UMA empresa; o gate de papel já protege)."""
    return get_object_or_404(Lot, pk=lot_pk)


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
_CAP_BYTES_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b', re.I)  # capacidade em bytes (TB adicionado 2026-06-26)


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
    # Tipo de label da FONTE ÚNICA (chips/chip_types.py) + fallback de substring,
    # que preserva casos legados (ex.: 'onenand' contém 'nand'). A GERAÇÃO do label
    # vem de canonical_gen(subtype) com fallback no chip_type via generation_of.
    kind = label_kind(canonical_chip_type(chip_type, result.get('subtype') or ''))

    if kind == 'umcp' or 'umcp' in ct:
        nand  = _extract_gb(result.get('emcp_nand', ''))
        ram   = _extract_gb(result.get('emcp_ram', ''))
        label = f"UMCP{nand}+{ram}" if nand else 'uMCP'
        return label, 'umcp'

    if kind == 'emcp' or 'emcp' in ct or result.get('is_emcp'):
        nand  = _extract_gb(result.get('emcp_nand', ''))
        ram   = _extract_gb(result.get('emcp_ram', ''))
        label = f"EMCP{nand}+{ram}" if nand else 'eMCP'
        return label, 'emcp'

    if kind == 'ufs' or 'ufs' in ct:
        # _format_cap preserva a unidade original: "128GB"→"128GB", "1TB"→"1TB".
        # Antes usava _extract_gb + "GB" hardcoded, o que produzia "UFS" (label vazio)
        # para chips 1TB — _extract_gb só reconhecia GB, não TB (fix 2026-06-26).
        cap   = _format_cap(result.get('capacity', ''))
        label = f"UFS{cap}" if cap else 'UFS'
        return label, 'ufs'

    if kind == 'emmc' or 'emmc' in ct:
        cap   = _format_cap(result.get('capacity', ''))
        label = f"EMMC{cap}" if cap else 'eMMC'
        return label, 'emmc'

    # GDDR antes do bloco DDR — 'ddr' in 'gddr3' seria True (substring), causando
    # falso-positivo. Samsung usa chip_type dedicado ("GDDR3"/"GDDR5"/etc.);
    # Hynix H5RS usa chip_type="RAM" com subtype="GDDR3" (coberto pelo elif).
    subtype_lower = (result.get('subtype') or '').lower()
    if kind == 'gddr' or 'gddr' in ct or ('gddr' in subtype_lower and ct in ('ram', 'dram', 'sdram')):
        gen  = canonical_gen(result.get('subtype') or '', chip_type) \
            or generation_of(chip_type, result.get('subtype') or '') or chip_type.upper()
        size = _density_g(result)
        label = f"{gen}+{size}G" if (gen and size) else (gen or 'GDDR')
        return label, 'gddr'

    if kind in ('lpddr', 'ddr', 'sdram') or 'lpddr' in ct or 'ddr' in ct or ct in ('ram', 'dram', 'sdram'):
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
            or generation_of(chip_type, result.get('subtype') or '') \
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

    if kind == 'nand' or 'nand' in ct:
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
    # i18n: 'id' e 'status' são CHAVES (lógica/CSS — nunca traduzir);
    # 'label' e 'detail' são EXIBIÇÃO (gettext, resolve no idioma da request).
    steps = [
        {'id': 'identificacao', 'label': _('Reconheci'),  'status': 'skip', 'detail': ''},
        {'id': 'fonte',         'label': _('Confirmado'), 'status': 'skip', 'detail': ''},
        {'id': 'rentabilidade', 'label': _('Rentável'),   'status': 'skip', 'detail': ''},
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
        steps[0].update(status='pass', detail=_('tipo/geração'))
        steps[1].update(status='fail',
                        detail=result.get('classification_source') or _('gramática'))
        steps[2].update(status='fail', detail=_('Geração não rentável'))
        return _out('reprovado', 'NÃO RENTÁVEL', by_generation=True)

    # ── 1. Identificação (specs reais) ───────────────────────────────────────
    if not has_cap:
        steps[0].update(status='fail', detail=_('specs ausentes'))
        return _out('desconhecido')
    steps[0].update(status='pass', detail=_('specs reais'))

    # ── 2. Fonte (confirmado no banco) — NÃO altera _is_confirmed ─────────────
    if not _is_confirmed(result):
        steps[1].update(status='fail',
                        detail=result.get('classification_source') or _('gramática'))
        return _out('fila')
    steps[1].update(status='pass', detail=_('banco de dados'))

    # ── 3. Rentabilidade (conservador: INDETERMINADO → aprovado) ─────────────
    profitable = assess_profitability(result)
    if profitable == 'NÃO RENTÁVEL':
        steps[2].update(status='fail', detail=_('Não rentável'))
        return _out('reprovado', profitable)

    # RENTÁVEL = verde "sim". INDETERMINADO ENTRA no estoque (regra conservadora), mas
    # NÃO é um "sim" confiante — ganha estado próprio ('warn'/âmbar) pra não mentir ao
    # operador (bug: antes recebia status='pass' e o frontend mostrava "Rentável: sim").
    if profitable == 'RENTÁVEL':
        steps[2].update(status='pass', detail=_('Rentável'))
    else:
        steps[2].update(status='warn', detail=_('Indeterminado (não avaliado)'))
    return _out('aprovado', profitable)


# ─── painel (home pós-login) ─────────────────────────────────────────────────

@role_required('operator')
def painel(request):
    """Home pós-login: responde "o que eu faço agora?" antes de jogar o usuário
    na lista de lotes. Padrão lançadeira (decisão de UX 2026-07-06): o lote
    ABERTO vira o CTA principal ("Continuar triagem"); sem lote aberto, o
    empty-state orienta por papel (gerente: abrir lote; operador: pedir ao
    gerente). Stats do dia são contexto, não o foco — o produto é a bancada.
    T3: tudo aqui passa a ser escopado por empresa via manager."""
    today = timezone.localdate()
    open_lots = list(Lot.objects.filter(status=Lot.STATUS_OPEN))
    ctx = {
        'open_lots': open_lots,
        'stats': {
            'open_count':     len(open_lots),
            'types_today':    InventoryEntry.objects.filter(added_at__date=today).count(),
            'pending_count':  PendingEntry.objects.count(),
            'rejected_today': RejectedEntry.objects.filter(created_at__date=today).count(),
        },
    }
    return render(request, 'estoque/painel.html', ctx)


# ─── lot list ───────────────────────────────────────────────────────────────

@role_required('operator')
def lot_list(request):
    # Todos os lotes (da empresa — T3 escopa via manager; hoje há uma empresa).
    # Antes filtrava por operator=request.user; ver docstring de _get_lot.
    lots = Lot.objects.all()
    return render(request, 'estoque/lotes.html', {'lots': lots})


# ─── lot create ─────────────────────────────────────────────────────────────

@role_required('manager')   # §8: abrir lote é de gerente+
@require_POST
def lot_create(request):
    description = request.POST.get('description', '').strip()
    # T2: numeração atômica por empresa (lock no contador da Company) — elimina
    # a corrida do antigo Max+1. request.company existe: o gate exige Membership.
    # T3: o lote nasce com a empresa (e a filial do gerente, se houver — §9).
    lot = Lot.open_for_company(request.company, request.user, description,
                               branch=request.membership.branch)
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


# ─── lot detail ─────────────────────────────────────────────────────────────

@role_required('operator')
def lot_detail(request, lot_pk):
    lot  = _get_lot(request, lot_pk)
    q    = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    entries   = _entries_for_display(lot, q, tipo)
    total_qty = sum(e.quantity for e in entries)

    ctx = {
        'lot':       lot,
        'entries':   entries,
        'total_qty': total_qty,
        'q':         q,
        'tipo':      tipo,
        # Marcas SUPORTADAS = as que têm família (classificam algo), direto do banco —
        # antes era lista hardcoded de 7 (com 'Toshiba' e sem Nanya/Kingston/Rayson).
        # Agora auto-atualiza: as 10 marcas dos yamls, Toshiba-Kioxia unificada, sem fantasmas.
        'brands': list(Brand.objects.filter(families__isnull=False)
                       .order_by('name').values_list('name', flat=True).distinct()),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'estoque/partials/table_body.html', ctx)

    # F8 (PRECIFICACAO §7): valoração do lote — SÓ admin, só no render completo.
    # Lote FECHADO mostra o CONGELADO (auditoria "vendi com qual tabela");
    # lote aberto calcula on-read da tabela viva (re-classifica cada PN).
    if getattr(request, 'company_role', None) == 'admin':
        ctx['valuations'] = _lot_valuations(request, lot)

    return render(request, 'estoque/estoque.html', ctx)


def _lot_valuations(request, lot):
    """[{buyer, frozen, totals…}] para o painel de valoração (admin-only)."""
    from pricing.engine import price_lot
    from pricing.models import Buyer, LotPricing

    out = []
    if lot.status == Lot.STATUS_CLOSED:
        for lp in LotPricing.objects.filter(lot=lot).select_related('buyer'):
            out.append({
                'buyer': lp.buyer, 'frozen': True, 'created_at': lp.created_at,
                'total_low': lp.total_low, 'total_mid': lp.total_mid,
                'total_high': lp.total_high,
                'priced_units': lp.priced_units, 'total_units': lp.total_units,
                'coverage_units': lp.coverage_units,
            })
        if out:
            return out
    for buyer in Buyer.objects.filter(active=True):
        rep = price_lot(lot, buyer)
        out.append({
            'buyer': buyer, 'frozen': False, 'created_at': None,
            'total_low': rep.totals['low'], 'total_mid': rep.totals['mid'],
            'total_high': rep.totals['high'],
            'priced_units': rep.priced_units, 'total_units': rep.total_units,
            'coverage_units': rep.coverage_units,
        })
    return out


# ─── lot close / reopen ──────────────────────────────────────────────────────

def _freeze_lot_pricing(request, lot):
    """F8 (PRECIFICACAO §1.7): congela a valoração no FECHAMENTO — o registro
    'vendi com qual tabela'. Um LotPricing por comprador ativo; reabrir+fechar
    cria outro (append). ⚠ Falha de preço NUNCA trava o fechamento do lote
    (operação da bancada > auditoria): loga e segue."""
    try:
        from pricing.engine import price_lot
        from pricing.models import Buyer, LotPricing
        for buyer in Buyer.objects.filter(active=True):
            rep = price_lot(lot, buyer)
            LotPricing.all_companies.create(
                lot=lot, buyer=buyer, closed_by=request.user,
                total_low=rep.totals['low'], total_mid=rep.totals['mid'],
                total_high=rep.totals['high'],
                priced_units=rep.priced_units, total_units=rep.total_units,
                priced_lines=rep.priced_lines, total_lines=rep.total_lines,
                lines=[{
                    'pn': l.part_number, 'qty': l.quantity,
                    'status': l.quote.status,
                    'min': str(l.quote.price_min) if l.quote.price_min is not None else None,
                    'max': str(l.quote.price_max) if l.quote.price_max is not None else None,
                    'reason': l.quote.reason, 'via': l.quote.via,
                } for l in rep.lines])
    except Exception:
        logger.exception('F8: falha ao congelar valoração do lote %s', lot.pk)


@role_required('manager')   # §8: fechar lote é de gerente+
@require_POST
def lot_close(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    lot.status    = Lot.STATUS_CLOSED
    lot.closed_at = timezone.now()
    lot.save(update_fields=['status', 'closed_at'])
    # O snapshot é criado no servidor mesmo quando quem fecha é o GERENTE —
    # ele não VÊ valores (§7); o registro é para o admin/auditoria.
    _freeze_lot_pricing(request, lot)
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


@role_required('manager')   # §8: reabrir lote é de gerente+
@require_POST
def lot_reopen(request, lot_pk):
    lot = _get_lot(request, lot_pk)
    lot.status    = Lot.STATUS_OPEN
    lot.closed_at = None
    lot.save(update_fields=['status', 'closed_at'])
    return redirect('estoque:lot_detail', lot_pk=lot.pk)


# ─── preview chip ────────────────────────────────────────────────────────────

@role_required('operator')
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

    # F8 (PRECIFICACAO §7/§12): preço do comprador na bancada — SÓ admin.
    # quotes_for_admin devolve [] para operador/gerente sem nem consultar preço.
    from pricing.engine import quotes_for_admin
    ctx['price_quotes'] = quotes_for_admin(request, result)

    return render(request, 'estoque/partials/confirm_card.html', ctx)


# ─── add chip ────────────────────────────────────────────────────────────────

@role_required('operator')   # §8: adicionar a lote ABERTO é o trabalho do operador
@require_POST
def add_chip(request, lot_pk):
    lot = _get_lot(request, lot_pk)

    if not lot.is_open:
        return HttpResponse(
            '<div class="est-msg est-msg--error" style="padding:12px 16px;border:1px solid #da1e28;color:#da1e28;margin-top:12px;">'
            + _('Este lote está fechado. Reabra-o para adicionar chips.')
            + '</div>'
        )

    pn  = _normalise_pn(request.POST.get('pn', ''))
    qty = max(1, int(request.POST.get('qty') or 1))

    if len(pn) < 4:
        return HttpResponse(
            '<div class="est-msg est-msg--error" style="padding:12px 16px;">' + _('PN inválido.') + '</div>'
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
            # ⚠ CANÔNICO — persistido p/ auditoria. NUNCA traduzir (i18n só na
            # exibição; dado gravado fica em pt-br — I18N.md §8.2).
            rejection_reason='NÃO RENTÁVEL (geração)',
            operator=request.user,
        )
        return render(request, 'estoque/partials/rejected_feedback.html', {
            'pn': pn, 'qty': qty,
            'chip_type': server_result.get('chip_type', ''),
            'capacity':  server_result.get('capacity', ''),
            'by_generation': True,
        })

    # has_cap recomputado NO SERVIDOR (regra de ouro #3): a identificação é decisão
    # de negócio (manda o chip para UnknownChip) e não pode confiar no hidden do
    # form. classify() é determinístico (lru_cache), então casa com o do preview;
    # um POST forjado não burla mais esta etapa.
    has_cap = _has_capacity(server_result)

    if not has_cap:
        # company: anotação §14.1 (fila global; 1ª empresa a reportar).
        UnknownChip.objects.get_or_create(
            part_number=pn, defaults={'company': request.company})
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
            # ⚠ CANÔNICO — persistido p/ auditoria. NUNCA traduzir (I18N.md §8.2).
            rejection_reason='NÃO RENTÁVEL',
            operator=request.user,
        )
        return render(request, 'estoque/partials/rejected_feedback.html', {
            'pn': pn, 'qty': qty,
            'chip_type': server_result.get('chip_type', ''),
            'capacity':  server_result.get('capacity', ''),
            'by_generation': False,
        })

    # Grava SEMPRE a partir do classify do SERVIDOR (server_result), não do POST
    # do cliente — fonte autoritativa, à prova de form forjado/defasado, e idêntica
    # ao que PendingEntry/RejectedEntry já fazem (linhas acima). _snapshot captura a
    # densidade DRAM em `capacity` (antes perdida → 'None') e limpa a geração do
    # `interface`. `confidence` não existe no InventoryEntry (só em Pending/Rejected).
    snap = _snapshot(server_result)
    snap.pop('confidence', None)
    # Passo 2: carimba a edição do catálogo do snapshot de intake (detecção de defasagem).
    from chips.models import CatalogVersion
    defaults = {**snap, 'quantity': qty, 'snapshot_catalog_version': CatalogVersion.current()}

    entry, created = InventoryEntry.objects.get_or_create(
        lot=lot, part_number=pn, defaults=defaults,
    )

    if not created:
        InventoryEntry.objects.filter(pk=entry.pk).update(
            quantity=F('quantity') + qty,
            last_updated=timezone.now(),
        )

    entries   = _entries_for_display(lot)
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

@role_required('operator')
@require_POST
def remove_entry(request, lot_pk, pk):
    lot   = _get_lot(request, lot_pk)
    # Operador só corrige lançamento em lote ABERTO (parte do fluxo de adicionar).
    # Mexer em lote fechado é correção de gestão → gerente+ (comportamento de
    # hoje preservado para o gerente; antes qualquer um removia de lote fechado).
    if not lot.is_open and not request.membership.has_role('manager'):
        raise PermissionDenied('Lote fechado: remoção é ação de gerente.')
    entry = get_object_or_404(InventoryEntry, pk=pk, lot=lot)
    qty   = max(1, int(request.POST.get('qty') or 1))

    if qty >= entry.quantity:
        entry.delete()
    else:
        InventoryEntry.objects.filter(pk=entry.pk).update(quantity=F('quantity') - qty)

    entries   = _entries_for_display(lot)
    total_qty = sum(e.quantity for e in entries)

    return render(request, 'estoque/partials/table_body.html', {
        'lot':       lot,
        'entries':   entries,
        'total_qty': total_qty,
    })


# ─── export xls ──────────────────────────────────────────────────────────────

@role_required('manager')   # §8: exportar lote é de gerente+
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
            timezone.localtime(entry.last_updated).strftime('%d/%m/%Y %H:%M:%S') if entry.last_updated else '—',
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

    filename = f'lote_{lot.number:03d}_{timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
