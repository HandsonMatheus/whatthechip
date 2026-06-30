"""
WhatTheChip — Engine de Classificação de Chips
===============================================
Classifica um Part Number em três camadas:

  1. Banco exato (KnownPart confirmado)  → resultado completo e verificado
       Só registros com confidence em (confirmed, manual) são autoritativos —
       verificados por humano/datasheet. Vencem a gramática.
  2. Gramática da família (ChipFamily)   → decodificação posicional do PN
       Cobre a cauda longa: qualquer PN não confirmado é decodificado pelas
       regras da família. O resultado é marcado pn_not_in_db (não confirmado).
  3. Fuzzy matching                      → sugestões para erros de digitação

Fonte da verdade:
    Um KnownPart só vence a gramática quando confidence ∈ (confirmed, manual).
    Não há enriquecimento automático: as specs vêm de confirmação manual
    (populate_*/import_*/fix_* + revisão no admin), nunca de IA. O antigo
    campo KnownPart.status (raw/enriched) e o fallback Gemini foram removidos.

Double-check:
    Quando o banco confirmado E a gramática têm resultados, eles são comparados.
    Divergência de capacidade é sinalizada como possível chip remarked.
"""

import json
import logging
import os
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

from django.db.models import CharField, Q, Value
from django.db.models.functions import Length, Replace

from .models import Brand, ChipFamily, DecodeMap, KnownPart, ProfitabilityConfig, SearchLog, Source, UnknownChip
from .chip_types import canonical_chip_type, profit_family
from .normalize import normalize_pn


# ── Fuzzy matching ─────────────────────────────────────────────────────────────

COMMON_CONFUSIONS = [
    ("O", "0"), ("I", "1"), ("B", "8"), ("V", "Y"), ("Z", "2"), ("S", "5"),
]

# ── Matriz de confusão visual — chips IC gravados a laser ──────────────────────
# Pares de caracteres visualmente ambíguos em silkscreen/laser de chips.
# Custo < 1.0 = confusão de leitura mais provável que substituição aleatória.
# Custo padrão para pares não listados = 1.0 (substituição arbitrária).
# Uso: _visual_edit_distance prioriza esses pares na ordenação fuzzy, garantindo
# que sugestões visualmente prováveis apareçam antes de vizinhos alfabéticos.
_CHIP_VISUAL_COST: dict = {
    frozenset({'O', '0'}): 0.1,   # letra O vs dígito zero — confusão mais comum
    frozenset({'O', 'Q'}): 0.1,   # Q tem cauda pequena; em laser de baixa resolução parece O
    frozenset({'Q', '0'}): 0.1,   # Q vs zero (mesma família circular)
    frozenset({'1', 'I'}): 0.1,   # um vs I maiúsculo
    frozenset({'B', '8'}): 0.1,   # B vs 8 — clássico do mercado de reciclagem
    frozenset({'L', '1'}): 0.2,   # L vs 1 em fontes sem serifa
    frozenset({'S', '5'}): 0.2,   # S vs 5
    frozenset({'Z', '2'}): 0.2,   # Z vs 2
    frozenset({'M', 'W'}): 0.2,   # M vs W (espelhado)
    frozenset({'U', 'V'}): 0.3,   # U vs V
    frozenset({'C', 'G'}): 0.3,   # C vs G (arco quase fechado)
    frozenset({'D', '0'}): 0.3,   # D vs zero em fontes monospace
    frozenset({'K', 'X'}): 0.4,   # K vs X em fontes comprimidas
}


def _edit_distance(a: str, b: str) -> int:
    """Distância de Levenshtein inteira (usada em paths não-FBGA)."""
    if len(a) > len(b):
        a, b = b, a
    distances = range(len(a) + 1)
    for c2 in b:
        distances_ = [distances[0] + 1]
        for i, c1 in enumerate(a):
            distances_.append(
                min(distances_[-1] + 1, distances[i + 1] + 1, distances[i] + (c1 != c2))
            )
        distances = distances_
    return distances[-1]


def _visual_edit_distance(a: str, b: str) -> float:
    """Distância de edição ponderada por confusão visual em chips IC.

    Similar ao Levenshtein padrão, mas substituições entre caracteres visualmente
    ambíguos em silkscreen/laser de chips custam < 1.0 (ver _CHIP_VISUAL_COST).
    Inserções e deleções sempre custam 1.0 — diferença de comprimento é objetiva.

    Resultado: candidatos visualmente prováveis (ex: O↔Q, B↔8, O↔0) ordenam-se
    ANTES de vizinhos alfabéticos aleatórios, mesmo com a mesma distância inteira.

    Exemplos para D9SGO:
        D9SGQ → 0.1  (O→Q, confusão visual — aparece primeiro)
        D9SG0 → 0.1  (O→0, confusão visual — aparece primeiro)
        D9SGB → 1.0  (O→B, sem confusão especial)
        D9SGG → 1.0  (O→G, sem confusão especial)
    """
    if a == b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    prev = [float(i) for i in range(len(a) + 1)]
    for c2 in b:
        curr = [prev[0] + 1.0]
        for j, c1 in enumerate(a):
            if c1 == c2:
                sub_cost = 0.0
            else:
                sub_cost = _CHIP_VISUAL_COST.get(frozenset({c1, c2}), 1.0)
            curr.append(min(
                curr[-1] + 1.0,       # inserção
                prev[j + 1] + 1.0,   # deleção
                prev[j] + sub_cost,  # substituição (visual)
            ))
        prev = curr
    return prev[-1]


# Níveis de confiança elegíveis para sugestão fuzzy/prefixo.
# Apenas registros verificados por humano ou datasheet oficial são sugeridos —
# evita que o operador seja direcionado a um PN estimado/distribuidor duvidoso.
_SUGGESTION_CONFIDENCE = ("confirmed", "manual")

# Níveis de confiança que VENCEM a gramática (autoridade / precedência). São os
# verificados por humano/datasheet. Ver _result_from_known() (human_verified).
_CONFIRMED_CONFIDENCE = ("confirmed", "manual")

# Gate de VISIBILIDADE do banco — substitui fielmente o antigo status="enriched".
# Um KnownPart entra na camada 1 (é reconhecido como registro do banco) quando
# REPRESENTA UM CHIP REAL: tem alguma capacidade preenchida (capacity / emcp_ram /
# emcp_nand / density_gbit), de QUALQUER confidence (confirmed, manual, distributor
# ou estimated); OU é confirmed/manual (humano avalizou o PN mesmo sem capacidade).
# Exclui placeholders vazios — a antiga "fila de revisão" raw, que tinha só
# chip_type e nenhuma capacidade.
#
# ⚠ VISIBILIDADE ≠ PRECEDÊNCIA. Distribuidor/estimado COM specs voltam a ser
# reconhecidos (known_exact=True), mas continuam SEM vencer a gramática completa:
# quem sobrepõe o decode posicional é só confirmed/manual (_result_from_known).
# Isto restaura o comportamento de quando o gate era status="enriched", que casava
# qualquer confidence desde que o registro estivesse enriquecido com dados.
_HAS_SPECS = (
    ~Q(capacity="") | ~Q(emcp_ram="") | ~Q(emcp_nand="") | ~Q(density_gbit="")
)
_USABLE = _HAS_SPECS | Q(confidence__in=_CONFIRMED_CONFIDENCE)


def _fuzzy_candidates(pn: str, threshold: int = 2) -> list:
    """Retorna KnownParts parecidos — ordena por distância visual (confusões comuns primeiro).
    Restrito a confidence confirmed/manual: só PNs verificados são sugeridos.
    """
    all_parts = (
        KnownPart.objects
        .filter(confidence__in=_SUGGESTION_CONFIDENCE)
        .values_list("part_number", flat=True)
    )
    matches = []
    for candidate in all_parts:
        if abs(len(candidate) - len(pn)) > threshold:
            continue
        dist = _visual_edit_distance(pn, candidate)
        if dist <= threshold:
            matches.append((dist, candidate))
    matches.sort()
    top_pns = [c for _, c in matches[:5]]
    if not top_pns:
        return []
    # BUG-5: substituído N+1 get() individuais por um único filter com select_related.
    parts_by_pn = {
        p.part_number: p
        for p in KnownPart.objects
            .filter(part_number__in=top_pns, confidence__in=_SUGGESTION_CONFIDENCE)
            .select_related("brand", "family")
    }
    return [parts_by_pn[c] for _, c in matches[:5] if c in parts_by_pn]


def _prefix_candidates(pn: str, min_prefix_len: int = 7) -> list:
    """Retorna KnownParts cujo part_number começa com o PN digitado.

    Cobre o caso de PN incompleto: o operador para de digitar antes do sufixo
    (ex: H5TQ2G83 → H5TQ2G83CFR, KMQ3100 → KMQ310006B-A).

    Diferente de _fuzzy_candidates: não compara por distância de edição —
    simplesmente filtra `part_number__startswith=pn`. Isso captura qualquer
    sufixo sem custo de edição alto demais (H5TQ2G83 vs H5TQ2G83CFR: diff=3,
    acima do threshold=2 do fuzzy, então o fuzzy nunca os capturaria).

    min_prefix_len evita retornar ruído para prefixos muito curtos (< 7 chars).
    Restrito a confidence confirmed/manual: só PNs verificados são sugeridos.
    Retorna lista de KnownPart objects (mesmo padrão que _fuzzy_candidates).
    """
    if len(pn) < min_prefix_len:
        return []
    return list(
        KnownPart.objects
        .filter(
            confidence__in=_SUGGESTION_CONFIDENCE,
            part_number__startswith=pn,
        )
        .exclude(part_number=pn)
        .select_related("brand", "family")
        .order_by("part_number")[:5]
    )


def _combined_suggestions(pn: str) -> list:
    """Combina sugestões de prefixo (PN incompleto) e fuzzy visual (typo).

    Prefixo vem primeiro — certeza maior, pois o digitado é literalmente o
    início do PN completo. Fuzzy completa a lista com confusões de caracteres.
    Retorna lista de strings (part_numbers), sem duplicatas, máx. 5 itens.

    Exemplos:
        H5TQ2G83    → [H5TQ2G83CFR, ...]  (prefixo: faltou o sufixo)
        D9SGO       → [D9SGQ, D9SG0, ...]  (fuzzy visual: O↔Q, O↔0)
        KMQ3100068  → [KMQ310006B, ...]    (fuzzy visual: 8↔B)
    """
    prefix = _prefix_candidates(pn)
    fuzzy  = _fuzzy_candidates(pn)
    seen: set = set()
    merged: list = []
    for s in prefix:
        if s.part_number not in seen:
            seen.add(s.part_number)
            merged.append(s.part_number)
    for s in fuzzy:
        if s.part_number not in seen:
            seen.add(s.part_number)
            merged.append(s.part_number)
    return merged[:5]


def _fuzzy_fbga_candidates(pn: str, threshold: int = 2) -> list:
    """Retorna códigos FBGA parecidos — ordena por distância visual (confusões comuns primeiro).

    Diferente de _fuzzy_candidates (que busca por part_number), esta função
    busca pelo campo fbga_code — necessário porque o operador digitou o código
    gravado a laser (ex: D9SGO) e queremos sugerir outros FBGAs próximos
    (ex: D9SGQ), não os PNs completos Micron (ex: MT52L...).

    Usa _visual_edit_distance: D9SGQ (O→Q, custo 0.1) ordena antes de D9SGB
    (O→B, custo 1.0), mesmo que ambos tenham Levenshtein inteiro = 1.

    Retorna lista de strings (os códigos FBGA), não objetos KnownPart.
    """
    all_fbga = (
        KnownPart.objects
        .filter(confidence__in=_SUGGESTION_CONFIDENCE)
        .exclude(fbga_code__isnull=True)
        .exclude(fbga_code="")
        .values_list("fbga_code", flat=True)
    )
    matches = []
    for candidate in all_fbga:
        if abs(len(candidate) - len(pn)) > threshold:
            continue
        dist = _visual_edit_distance(pn, candidate)
        if dist <= threshold:
            matches.append((dist, candidate))
    matches.sort()
    return [c for _, c in matches[:5]]


# ── Carimbo de edição do catálogo (cache POR VERSÃO) ──────────────────────────
#
# O cache do engine é keyed no `catalog_version` (chips/models.py::CatalogVersion).
# Quando a gramática muda (populate_*/admin), o carimbo sobe (sinais em apps.py) e
# cada worker do gunicorn recarrega o catálogo SOZINHO na leitura seguinte — sem
# reinício. (Antes: `lru_cache` sem argumento → a chave nunca mudava, e o servidor
# servia gramática velha até reiniciar — a antiga "regra de ouro #3".)

def _catalog_version() -> int:
    """Edição atual do catálogo. Fallback 0 se a tabela ainda não existe (durante
    o primeiro migrate / em testes antes da migração)."""
    try:
        from .models import CatalogVersion
        return CatalogVersion.current()
    except Exception:
        return 0


# ── Mapa de decodificação ──────────────────────────────────────────────────────
@lru_cache(maxsize=512)
def _decode_map_for_version(version: int, map_name: str) -> dict:
    rows = DecodeMap.objects.filter(map_name=map_name).values("char_key", "val_primary", "val_secondary")
    return {r["char_key"]: (r["val_primary"], r["val_secondary"]) for r in rows}


def _load_decode_map(map_name: str) -> dict:
    """Mapa de decodificação (cacheado por edição do catálogo)."""
    return _decode_map_for_version(_catalog_version(), map_name)


# ── Match de família ──────────────────────────────────────────────────────────
@lru_cache(maxsize=8)
def _families_for_version(version: int) -> list:
    """Famílias ativas, ordenadas por prioridade e comprimento (cache por versão)."""
    return list(
        ChipFamily.objects
        .filter(active=True)
        .annotate(prefix_len=Length("prefix"))
        .order_by("priority", "-prefix_len")
        .select_related("doc_page")
    )


def _get_all_families() -> list:
    """Todas as famílias ativas, ordenadas (cacheado por edição do catálogo)."""
    return _families_for_version(_catalog_version())


def _match_family(pn: str):
    """Retorna ChipFamily com o prefixo mais longo que bater no PN."""
    for fam in _get_all_families():
        if pn.startswith(fam.prefix):
            return fam
    return None


def clear_engine_cache():
    """Invalida os caches em memória do engine. (Hoje o carimbo `catalog_version`
    já auto-invalida em todos os workers; mantido para os populate_* existentes e
    para os testes.)"""
    _decode_map_for_version.cache_clear()
    _families_for_version.cache_clear()


# ── URL da documentação ────────────────────────────────────────────────────────

def _doc_url(family) -> str | None:
    """Retorna a URL da página de documentação ligada à família, se existir."""
    if family and family.doc_page_id:
        try:
            return family.doc_page.get_absolute_url()
        except Exception:
            pass
    return None


# ── EMCP_RAM_TYPES — decodificação de tipo RAM Samsung legacy ─────────────────
#
# ESCOPO: EXCLUSIVAMENTE famílias Samsung sem decode_gen_map configurado.
#         (Caminho 3 do bloco eMCP — ver comentário abaixo.)
#
# ISOLAMENTO GARANTIDO POR CÓDIGO: o engine só consulta este dicionário quando
# fam.decode_gen_map está vazio/None. Qualquer família de qualquer marca que
# tenha decode_gen_map configurado NUNCA chega aqui — mesmo que o lookup
# no mapa próprio falhe (Caminho 2 retorna mensagem neutra em vez disso).
#
# Letras: convenção Samsung — 3ª posição do PN (ex: KM[R]x1000B → R=LPDDR4/4X).
# Famílias modernas Samsung (KMG, KML, KMD…) têm decode_gen_map="SAM_EMCP_GEN"
# e portanto também não chegam aqui.
# V=LPDDR2 porque o único prefixo legacy sem decode_gen_map que usa V é o
# KMV (Samsung eMCP 2010-2013, LPDDR2) — não confundir com uMCP moderno.

EMCP_RAM_TYPES = {
    # LPDDR / LPDDR2 (legado)
    "J": "LPDDR (legado)",
    "Z": "LPDDR2 / LPDDR (?)",
    "K": "LPDDR2 (legado)",
    "Y": "LPDDR2",
    "V": "LPDDR2 (legado)",   # KMV antigo (2010-2013) — NÃO confundir com uMCP moderno
    # LPDDR3
    "Q": "LPDDR3",
    "F": "LPDDR3",
    "N": "LPDDR3",
    "G": "LPDDR3",
    # LPDDR4 / LPDDR4X
    # R = assinatura oficial Samsung para LPDDR4/LPDDR4X (série KMR, Galaxy A 2016-2019).
    # Confirmado via datasheets: KMRH60014A-B614 (A7 2017) = LPDDR4; KMRY60014A = LPDDR4.
    # A confusão anterior vinha do prefixo KMRP (KMRP6001AM, S5 Mini) que é LPDDR3 —
    # mas KMRP é uma sub-série legada; na codificação padrão KMR a 3ª letra R = LPDDR4.
    "R": "LPDDR4/4X",
    # S = LPDDR1 — letra de família KMS (legado 2012-2013, Galaxy Centura era).
    # NÃO confundir com SAM_EMCP_GEN['S']="LPDDR4X" (esse mapa é para famílias
    # com decode_gen_map configurado; EMCP_RAM_TYPES só é consultado quando
    # decode_gen_map está vazio — Caminho 3 do engine).
    "S": "LPDDR1",
    "D": "LPDDR4X",
    "E": "LPDDR4/4X",
    # LPDDR5
    "L": "LPDDR5",
}


# ── Regex de capacidade (usada em múltiplos lugares) ──────────────────────────
# T (terabyte) incluído a partir de 2026-06-26 para suportar UFS 1TB+ (Kioxia).
# (?:\.\d+)? incluído em 2026-06-27 para suportar capacidades decimais (ex.: "1.5GB").
# Sem isso, re.search("(\d+)\s*([TGMK])B", "1.5GB") casa "5GB" → retorna 5.0
# em vez de 1.5, fazendo chips abaixo do threshold serem marcados RENTÁVEL.
# Chip revelador: K4E2E304EA (LPDDR3 1.5GB Samsung) → extract_gib retornava 5.0.
_CAP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([TGMK])B", re.I)

# ── Regex de detecção de código FBGA ─────────────────────────────────────────
# Padrão Micron: 5 caracteres alfanuméricos, 2º char numérico.
# DRAM mobile (LPDDR3/4/4X): D9XXX  ex: D9VFC, D9TBH, D9WFJ, D9SHD
# NAND / flash:               D8XXX  ex: D8TXF, D8WXW
# eMCP / LPDDR / eMMC / UFS:  JWB11, JY106, JY938, etc. (duas letras no início)
#
# Padrão ampliado: qualquer 5 chars alfanuméricos começando com letra maiúscula.
# Critério de não-conflito com PNs reais: PNs têm 8+ chars (MT53B..., MTFC...).
_FBGA_RE = re.compile(r'^[A-Z][A-Z0-9]{4}$')

# ── Regex para geração LPDDR / DDR (usada em assess_profitability) ────────────
_LPDDR_GEN_RE = re.compile(r'LPDDR(\d+)?', re.I)
_DDR_GEN_RE   = re.compile(r'(?<![A-Z])DDR(\d+)?', re.I)  # DDR mas não LPDDR
# Nota: _DDR_GEN_RE é usado com findall() para capturar TODAS as ocorrências
# (ex: "DDR DDR3/DDR3L" → [gen1, gen3, gen3]) e retornar o máximo.
# search() pegaria apenas o "DDR" genérico do chip_type e devolveria geração 1.

# Gigabits (case-sensitive: "Gb" ≠ "GB") — para densidade DRAM ex: "8Gb = 1GB por die"
_GBIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*Gb\b')


def _clean(s: str) -> str:
    """Normaliza espaços internos e trim.

    Garante que strings vindas do banco (às vezes com espaços duplos,
    ex: 'eMMC   8GB', 'LPDDR2  1GB') fiquem legíveis na UI.
    """
    return " ".join(str(s or "").split())


# ── Resultado base da família ──────────────────────────────────────────────────

def _result_from_family(pn: str, fam) -> dict:
    """Decodifica o PN usando as regras da família. Retorna resultado parcial."""
    # BUG-4: json.loads defensivo — JSON inválido no admin não crasha o engine.
    try:
        _reasoning = json.loads(fam.reasoning) if fam.reasoning else []
    except (json.JSONDecodeError, TypeError):
        logger.warning("JSON inválido em ChipFamily.reasoning para prefix=%s", fam.prefix)
        _reasoning = []

    r = {
        "pn":            pn,
        "known":         True,
        "known_exact":   False,
        "chip_type":     fam.chip_type,
        "subtype":       fam.subtype,
        "interface":     fam.interface,
        "family_prefix": fam.prefix,
        "brand":         fam.brand.name,
        "is_emcp":       fam.is_emcp,
        "tip":           fam.tip or "",
        "reasoning":     _reasoning,
        "doc_url":       _doc_url(fam),
        "capacity":      None,
        "dram_density":  None,
        "emcp_ram":      None,
        "emcp_nand":     None,
        "emcp_device":   None,
        "emcp_source":   None,
        "device":        None,
        "confidence":         "estimated",
        "source_url":         None,
        "from_web":           False,
        "suffix_note":        None,
        "remarked_flag":      False,
        "fuzzy_suggestions":  [],
        "classification_source": "gramática",
        # Família sem documentação pública verificável (ex: H28M).
        # True ativa banner de contribuição na UI.
        "family_undocumented": not getattr(fam, "is_documented", True),
    }

    # ── Geração / tipo RAM (decode_gen_map) ──────────────────────────────────
    # Funciona tanto para eMMC (geração: "eMMC 5.1") quanto para eMCP.
    # Para Samsung eMCP: chave de 1 char → tipo RAM (ex: "R"→"LPDDR4/4X").
    # Para SK Hynix eMCP: chave de 2 chars → RAM completa (ex: "AC"→"LPDDR3 4GB").
    # decode_gen_len controla o comprimento da chave (padrão=1 para compat Samsung).
    _decoded_gen = None
    if fam.decode_gen_pos is not None and fam.decode_gen_map:
        gen_map = _load_decode_map(fam.decode_gen_map)
        pos     = fam.decode_gen_pos
        gen_len = (fam.decode_gen_len or 1)
        if len(pn) >= pos + gen_len:
            entry = gen_map.get(pn[pos:pos + gen_len])
            if entry:
                _decoded_gen = entry[0]  # ex: "LPDDR4/4X", "eMMC 5.1", "LPDDR3 4GB"
                if not fam.is_emcp:
                    r["interface"] = _decoded_gen  # eMMC/UFS: seta interface direto

    # ── Capacidade eMMC / UFS / NAND (não-eMCP) ──────────────────────────────
    if fam.decode_cap_pos is not None and fam.decode_cap_map and not fam.is_emcp:
        cap_map = _load_decode_map(fam.decode_cap_map)
        pos = fam.decode_cap_pos
        cap_len = fam.decode_cap_len if fam.decode_cap_len and fam.decode_cap_len > 1 else 1
        if len(pn) >= pos + cap_len:
            key = pn[pos:pos + cap_len]
            entry = cap_map.get(key)
            if entry:
                r["capacity"] = entry[0]

    # ── eMCP / uMCP: capacidade dual via mapa ─────────────────────────────────
    # Cada marca tem seus próprios mapas — o engine nunca mistura dados entre marcas.
    #
    # NAND: decode_cap_map + decode_cap_len → val_primary = capacidade NAND
    # RAM:  decode_gen_map + decode_gen_len → val_primary = tipo+capacidade RAM
    #       (ou val_secondary do NAND map para padrão Samsung com chave única)
    #
    # Fallback EMCP_RAM_TYPES (Samsung legacy) só é ativado quando
    # fam.decode_gen_map está vazio — garantido por código, ver bloco abaixo.
    if fam.is_emcp:
        _nand_cap = None
        _ram_cap  = None

        if fam.decode_cap_pos is not None and fam.decode_cap_map:
            cap_map = _load_decode_map(fam.decode_cap_map)
            pos = fam.decode_cap_pos
            cap_len = fam.decode_cap_len if fam.decode_cap_len and fam.decode_cap_len > 1 else 1
            if len(pn) >= pos + cap_len:
                key = pn[pos:pos + cap_len]
                entry = cap_map.get(key)
                if entry:
                    _nand_cap = entry[0] or None   # ex: "64GB"
                    _ram_cap  = entry[1] or None   # ex: "4GB"

        # Tipo RAM — três caminhos mutuamente exclusivos:
        #
        # Caminho 1 — decode_gen_map configurado E chave encontrada
        #   Qualquer marca que tenha decode_gen_map usa seu próprio mapa.
        #   Resultado: o que o mapa retornar (ex: "LPDDR4/4X", "LPDDR3 4GB").
        #
        # Caminho 2 — decode_gen_map configurado MAS chave ausente do mapa
        #   A família tem mapa próprio mas o código desse PN ainda não foi catalogado.
        #   Extrai o tipo LPDDR do subtype como melhor esforço e sinaliza ao operador.
        #   NUNCA consulta EMCP_RAM_TYPES — esse dicionário é exclusivo Samsung.
        #
        # Caminho 3 — decode_gen_map NÃO configurado (famílias Samsung legacy)
        #   Decodifica pela 3ª letra do PN (convenção exclusiva Samsung: KMR→R=LPDDR4/4X).
        #   EMCP_RAM_TYPES só é acessado aqui — nunca para outras marcas.
        if _decoded_gen:
            # Caminho 1: mapa próprio retornou resultado (qualquer marca)
            ram_type = _decoded_gen
        elif fam.decode_gen_map:
            # Caminho 2: família tem mapa próprio, código ainda não catalogado.
            # Extrai tipo LPDDR do subtype (ex: "eMCP LPDDR3" → "LPDDR3").
            m = re.search(r'LPDDR[\dX/]+', fam.subtype or '')
            ram_type = (
                f"{m.group(0)} (código não mapeado — atualizar populate)"
                if m else "RAM não mapeada — consultar datasheet"
            )
        else:
            # Caminho 3: Samsung legacy sem decode_gen_map (KMV, KMJ, KMQ antigo…)
            # Convenção de letra na 3ª posição do PN — exclusiva Samsung.
            ram_char = pn[2] if len(pn) > 2 else "?"
            if ram_char.isdigit():
                # Família numérica Samsung (KM4, KM8, KM5…): o dígito é parte do prefixo,
                # não letra de geração. Extrai tipo do subtype da família.
                m = re.search(r'LPDDR[\dX/]+', fam.subtype or '')
                ram_type = m.group(0) if m else "LPDDR"
            else:
                ram_type = EMCP_RAM_TYPES.get(ram_char, f"tipo '{ram_char}' — consultar datasheet")

        # Versão NAND eMMC/UFS: usa a parte ANTES do "+" da interface.
        # fam.interface para eMCP SK Hynix contém a string combinada (ex: "eMMC 5.1 + LPDDR4X").
        # Para emcp_nand só queremos a parte NAND — "eMMC 5.1" ou "UFS 2.1".
        # BUG-7 FIX: sem o split, emcp_nand ficava "eMMC 5.1 + LPDDR4X 128GB" (LPDDR vaza no campo NAND).
        nand_version = (fam.interface or "eMMC").split("+")[0].strip()

        # Monta strings finais
        if _nand_cap:
            r["emcp_nand"] = f"{nand_version} {_nand_cap}".strip()
        else:
            # Decode incompleto: tipo sem capacidade numérica.
            # Label explícito para o operador não confundir com dado real —
            # "eMMC 5.0" sem GB é INDISTINGUÍVEL de "eMMC 5.0 64GB" no estoque.
            # Adicionar mais entradas ao decode map (populate_micron_mcp --overwrite)
            # ou enriquecer via fill_capacity_from_micron_api para resolver.
            r["emcp_nand"] = f"{nand_version} ⚠ cap. não mapeada"

        if _ram_cap:
            r["emcp_ram"] = f"{ram_type} {_ram_cap}".strip()
        elif _CAP_RE.search(ram_type):
            # BUG-7 FIX: gen map SK Hynix já embute capacidade no val_primary
            # (ex: HYX_LPDDR4X_RAM_CAP: "AE" → "LPDDR4X 6GB").
            # Como _ram_cap vem do val_secondary (vazio nesses mapas), caia no else
            # e adicionava "⚠ cap. não mapeada" a um string que já tinha a capacidade.
            r["emcp_ram"] = ram_type
        else:
            r["emcp_ram"] = f"{ram_type} ⚠ cap. não mapeada"

        # Considera decode completo se:
        #   - NAND via decode_cap_map E RAM via val_secondary (padrão Samsung), OU
        #   - NAND via decode_cap_map E RAM via decode_gen_map com capacidade embutida
        #     (padrão SK Hynix: "LPDDR3 4GB" vem do gen map, _ram_cap é None).
        _ram_from_gen = _decoded_gen and bool(_CAP_RE.search(_decoded_gen))
        r["emcp_source"] = "gramática" if (_nand_cap and (_ram_cap or _ram_from_gen)) else "parcial (gramática)"

        # interface já está codificada em emcp_nand (ex: "eMMC 5.1 64GB").
        # Exibi-la separadamente causaria redundância/confusão na UI ("Interface: LPDDR+eMMC").
        r["interface"] = ""

        # Sincroniza `subtype` com o tipo RAM decodificado pelo gen map (Caminho 1).
        # Sem isso, subtype fica com o default da família (ex: "LPDDR3" para MT29TZZZ),
        # enquanto emcp_ram já contém o tipo correto (ex: "LPDDR2 1GB"). Necessário
        # para MT29TZZZ Gen A onde o tipo varia por PN (dígito→LPDDR2, letra→LPDDR3+).
        # Só sincroniza quando _decoded_gen é tipo limpo (sem capacidade embutida) para
        # não tornar subtype = "LPDDR4X 6GB" (SK Hynix embute capacidade no gen map).
        if _decoded_gen and not _CAP_RE.search(_decoded_gen):
            r["subtype"] = _decoded_gen

    # ── Densidade DRAM ───────────────────────────────────────────────────────
    # Modo escolhido por ChipFamily.decode_density_type (DADO, por família — mesma
    # filosofia do resto do decode: lógica genérica no engine, config no populate):
    #   'pc' / 'mobile' → lookup posicional num DecodeMap (DRAM_PC / DRAM_MOBILE);
    #   'micron'        → FÓRMULA depth×width (nomenclatura JEDEC da Micron).
    # Adicionar um modo aqui (uma vez) cobre uma família/marca inteira sem código
    # novo por marca.
    if fam.decode_density_type and not fam.is_emcp:
        dtype = fam.decode_density_type
        if dtype in ("pc", "mobile"):
            density_map = _load_decode_map("DRAM_PC" if dtype == "pc" else "DRAM_MOBILE")
            if dtype == "pc" and len(pn) >= 5:
                code = pn[3:5]
                entry = density_map.get(code)
                if entry and entry[0]:
                    conf = "✓" if code in ("4G", "8G", "16", "32", "64") else "~"
                    r["dram_density"] = f"{entry[0]} = {entry[1]} por die [{conf}]"
                else:
                    r["dram_density"] = f"Código '{code}' não mapeado — consultar datasheet"
            elif dtype == "mobile" and len(pn) >= 4:
                code = pn[3]
                entry = density_map.get(code)
                if entry and entry[0]:
                    conf = "✓" if code in ("4", "8", "G", "H") else "~"
                    r["dram_density"] = f"{entry[0]} = {entry[1]} por die [{conf}]"
                else:
                    r["dram_density"] = f"Código '{code}' não mapeado — consultar datasheet"
        elif dtype == "micron":
            # FÓRMULA (Micron LPDDR/DDR MT4x/MT5x/MT6x): o bloco
            # [profundidade][unidade M|G][largura] após o prefixo dá a densidade
            # TOTAL do dispositivo = profundidade × largura. Capacidade do pacote
            # = total ÷ 8. ⚠ O sufixo D{N} (dies/canais) NÃO multiplica — o total já
            # é depth×width (datasheet Micron: MT53E768M32D4 = 24Gb total = 3GB, nunca
            # 96Gb/12GB). Mesma conta de fix_micron_capacity e MICRON.md, agora no
            # classify() — cobre toda a cauda MT5x de uma vez, sem script offline.
            mm = re.match(r"^MT\d{2}[A-Z]+?(\d+)([MG])(\d+)", pn)
            if mm:
                rows, unit, bus = int(mm.group(1)), mm.group(2).upper(), int(mm.group(3))
                total_gbit = rows * (1024 if unit == "G" else 1) * bus // 1024
                gb = total_gbit / 8
                if gb >= 1:
                    r["capacity"] = f"{int(gb)}GB" if gb == int(gb) else f"{gb:.1f}GB"
                else:
                    r["capacity"] = f"{int(round(gb * 1024))}MB"
                r["dram_density"] = f"{total_gbit}Gb total [✓]"

    # ── Sufixo ───────────────────────────────────────────────────────────────
    if fam.suffix_rules:
        try:
            sfx = json.loads(fam.suffix_rules)
        except (json.JSONDecodeError, TypeError):
            logger.warning("JSON inválido em ChipFamily.suffix_rules para prefix=%s", fam.prefix)
            sfx = {}
        for s, data in sfx.items():
            if pn.endswith(s):
                r["suffix_note"] = data.get("note", "")
                break
        else:
            r["suffix_note"] = f"Sufixo não mapeado — verificar: {list(sfx.keys())}"

    return r


def _result_from_known(pn: str, known, fam) -> dict:
    """
    Sobrepõe resultado da família com dados do KnownPart.

    Prioridade:
      - confirmed / manual / distributor → DB sempre vence (verificado por humano)
      - ai_* / estimated + gramática completa → gramática vence
        (corrigir o gabarito corrige o resultado imediatamente, sem re-enriquecer)
      - gramática incompleta → DB complementa
    """
    r = _result_from_family(pn, fam)

    # Verifica se a gramática produziu resultado completo (decode posicional total)
    grammar_emcp_ok = fam.is_emcp and bool(
        _CAP_RE.search(str(r.get("emcp_ram")  or "")) and
        _CAP_RE.search(str(r.get("emcp_nand") or ""))
    )
    grammar_cap_ok = (not fam.is_emcp) and bool(
        _CAP_RE.search(str(r.get("capacity") or r.get("dram_density") or ""))
    )
    grammar_complete = grammar_emcp_ok or grammar_cap_ok

    # Entradas verificadas por humano sempre vencem a gramática.
    # ATENÇÃO: "distributor" foi removido daqui intencionalmente.
    # Dados de distribuidor (wolfchip, censtry, aliexpress, etc.) são raspados
    # por robôs e frequentemente contêm erros de capacidade RAM. A gramática
    # interna (baseada na codificação oficial Samsung) é mais confiável que
    # qualquer catálogo de atacadista. Distribuidor só complementa quando a
    # gramática está incompleta (cap_key ausente do mapa).
    human_verified = known.confidence in ("confirmed", "manual")

    # Gramática vence DB para campos técnicos quando: resultado completo + não verificado
    grammar_wins = grammar_complete and not human_verified

    if fam.is_emcp:
        if grammar_wins:
            # Gramática completa: usa resultado integral (RAM type + capacidade).
            r["emcp_source"] = r.get("emcp_source", "gramática")
        else:
            # Gramática incompleta: DB complementa campos faltantes.
            #
            # Tipo RAM quando decode_gen_map está configurado:
            #   - Não verificado por humano (ai_*, estimated, distributor):
            #       Tipo da gramática prevalece sobre o DB — distribuidores frequentemente
            #       têm tipos desatualizados (ex: "LPDDR3" para chip LPDDR4X).
            #   - Verificado por humano (confirmed / manual):
            #       DB é autoridade total — tipo E capacidade do DB são usados.
            #       A gramática pode estar errada para exceções de família
            #       (ex: KMR310001M = LPDDR3, mas R no SAM_EMCP_GEN → LPDDR4/4X).
            grammar_ram = r.get("emcp_ram") or ""
            if fam.decode_gen_map and grammar_ram and not _CAP_RE.search(grammar_ram) and not human_verified:
                # Gramática tem o TIPO mas não a capacidade (cap_key ausente do mapa).
                # Complementa com a capacidade que o DB já tem.
                # Só aplicado quando não verificado por humano: se confidence=confirmed,
                # o DB tem tipo E capacidade corretos — usamos o DB inteiro (cai no else abaixo).
                db_ram = _clean(known.emcp_ram) or ""
                cap_match = _CAP_RE.search(db_ram)
                if cap_match:
                    r["emcp_ram"]    = f"{grammar_ram} {cap_match.group(0)}"
                    r["emcp_source"] = "gramática+db"
                else:
                    # DB também não tem capacidade — deixa o tipo parcial
                    r["emcp_source"] = "gramática (cap. não mapeada)"
            else:
                # DB vence na capacidade.
                #
                # Quando NÃO verificado por humano (ai_*, estimated, distributor):
                #   O TIPO RAM é definido pelo decode_gen_map da família — distribuidores
                #   e IA frequentemente têm o tipo errado (ex: "LPDDR3" para chip LPDDR4X).
                #   Neste caso, combinamos o tipo da gramática com a capacidade do DB.
                #
                # Quando verificado por humano (confirmed / manual):
                #   O DB é totalmente confiável — não sobrescrever tipo nem capacidade.
                #   Ex: KMR310001M tem confidence=confirmed com LPDDR3 2GB no banco.
                #   A gramática diz LPDDR4/4X 1GB (errado — exceção de família).
                #   Forçar grammar_type aqui produziria "LPDDR4/4X 2GB" — tipo incorreto.
                db_ram = _clean(known.emcp_ram) or ""
                if fam.decode_gen_map and grammar_ram and not human_verified:
                    # Não-humano: tipo da gramática corrige o DB (proteção contra dados de distribuidor)
                    grammar_type = grammar_ram.split()[0]   # ex: "LPDDR4X"
                    cap_match    = _CAP_RE.search(db_ram)
                    if cap_match and grammar_type:
                        r["emcp_ram"] = f"{grammar_type} {cap_match.group(0)}"
                    else:
                        r["emcp_ram"] = db_ram or r["emcp_ram"]
                else:
                    # Humano-verificado (confirmed/manual): DB é autoridade quando tem capacidade.
                    #
                    # BUG-6 FIX: Se DB tem apenas tipo sem capacidade (ex: "LPDDR3") mas a gramática
                    # decodificou tipo+capacidade (ex: "LPDDR2 1GB"), usa a gramática.
                    # Cenário típico: chip confirmado via enrich_micron_fbga antes da chave "8D5"
                    # existir no MIC_MCP_CAP. O DB ficou com "LPDDR3" (incompleto) + tipo errado.
                    # Após populate_micron_mcp --overwrite, a gramática produz o resultado correto
                    # mas o DB "confirmado" impedia o override. Esta regra corrige isso.
                    if db_ram and _CAP_RE.search(db_ram):
                        # DB tem tipo E capacidade → DB é autoridade (ex: KMR310001M LPDDR3 2GB)
                        r["emcp_ram"] = db_ram
                    # else: DB vazio ou sem capacidade → mantém valor da gramática (já em r["emcp_ram"])
                r["emcp_source"] = known.confidence

            # NAND: a interface física (UFS vs eMMC) é definida pela família,
            # não pelo banco de dados. Distribuidores frequentemente preenchem
            # "eMMC" para chips uMCP UFS por copy-paste de catálogo genérico.
            db_nand   = _clean(known.emcp_nand) or ""
            _gram_nand = r.get("emcp_nand") or ""
            if db_nand:
                if fam.interface and "UFS" in fam.interface and "eMMC" in db_nand:
                    # BUG-2: Família é UFS mas DB diz "eMMC" → corrige o rótulo
                    # preservando apenas a capacidade numérica.
                    # Antes: db_nand.replace("eMMC", fam.interface.split()[0])
                    #   → perdia a versão ("UFS 3.1" virava "UFS") ou gerava
                    #   versão errada ("UFS 5.1 32GB" quando DB tinha "eMMC 5.1 32GB").
                    # Agora: extrai o número de capacidade e reconstrói com interface completa.
                    _nand_cap_match = _CAP_RE.search(db_nand)
                    # BUG-7 FIX: fam.interface pode conter "+ LPDDR4X" (ex: "UFS 2.1 + LPDDR4X").
                    # Para emcp_nand usar apenas a parte UFS/eMMC antes do "+".
                    _nand_iface = (fam.interface or "").split("+")[0].strip() or (fam.interface or "UFS")
                    if _nand_cap_match:
                        r["emcp_nand"] = f"{_nand_iface} {_nand_cap_match.group(0)}"
                    else:
                        r["emcp_nand"] = _nand_iface  # sem capacidade: ao menos corrige interface
                elif not _CAP_RE.search(db_nand) and _CAP_RE.search(_gram_nand):
                    # BUG-6: DB tem NAND sem número de capacidade (ex: "eMMC 5.0") mas gramática
                    # decodificou a capacidade (ex: "eMMC 5.0 8GB"). Manter gramática.
                    # Ocorre após populate --overwrite preencher chave antes inexistente (ex: "8D5").
                    pass  # mantém _gram_nand que já está em r["emcp_nand"]
                else:
                    r["emcp_nand"] = db_nand
            # (se db_nand vazio, mantém o valor da gramática)

        # ── BUG-3: Micron MCP — interface correta via source_url ────────────
        #
        # PROBLEMA: A família MT29VZZZ tem chip_type="eMCP" e interface="eMMC 5.1"
        # como padrão, mas a família cobre DOIS tipos de chips fisicamente distintos:
        #   - emmc-based-mcp → eMCP: NAND eMMC + LPDDR4 RAM (bancada eMMC)
        #   - ufs-based-mcp  → uMCP: NAND UFS  + LPDDR4 RAM (bancada UFS)
        #
        # Usar o chip UFS no programador eMMC causa dano permanente ao hardware.
        #
        # SOLUÇÃO: A API FBGA da Micron classifica cada chip na URL do produto:
        #   "...multichip-packages/ufs-based-mcp/..."  → uMCP / UFS 2.2
        #   "...multichip-packages/emmc-based-mcp/..." → eMCP / eMMC 5.1
        #
        # Quando source_url indica UFS mas emcp_nand foi montado como "eMMC 5.1 xxGB"
        # (pela gramática usando fam.interface="eMMC 5.1"), corrigimos aqui.
        # Mesma lógica para emmc-based-mcp quando a família for uMCP (ex: MT30AZZZ
        # com algumas variantes eMMC futuras).
        #
        # Prioridade: source_url da API Micron > fam.interface > gramática.
        # Aplica-se APENAS a chips com source_url da API Micron (confidence=confirmed
        # via enrich_micron_fbga). Não afeta chips sem source_url ou de outras fontes.
        if known.source_url:
            _src = known.source_url
            if "ufs-based-mcp" in _src:
                # source_url confirma: é chip UFS-based (uMCP)
                _nand_str = r.get("emcp_nand") or ""
                if "eMMC" in _nand_str:
                    # Gramática/família disse eMMC mas Micron diz UFS — corrige
                    _cap_m = _CAP_RE.search(_nand_str)
                    _cap_s = f" {_cap_m.group(0)}" if _cap_m else ""
                    r["emcp_nand"] = f"UFS 2.2{_cap_s}"
                r["chip_type"] = "uMCP"
                r["is_emcp"]   = True   # continua sendo chip composto (NAND+RAM)
            elif "emmc-based-mcp" in _src:
                # source_url confirma: é chip eMMC-based (eMCP)
                _nand_str = r.get("emcp_nand") or ""
                if "UFS" in _nand_str:
                    # Família disse UFS mas Micron diz eMMC — corrige
                    _cap_m = _CAP_RE.search(_nand_str)
                    _cap_s = f" {_cap_m.group(0)}" if _cap_m else ""
                    r["emcp_nand"] = f"eMMC 5.1{_cap_s}"
                r["chip_type"] = "eMCP"
                r["is_emcp"]   = True

        r["emcp_device"] = known.device or None
        r["source_url"]  = known.source_url
    else:
        if not grammar_wins:
            if known.capacity:
                r["capacity"] = _clean(known.capacity)
            if known.density_gbit:
                _dgb = known.density_gb
                r["dram_density"] = (
                    f"{known.density_gbit} = {_dgb} por die [✓]"
                    if _dgb else f"{known.density_gbit} por die [✓]"
                )
        if known.device:
            r["device"] = known.device

    r["confidence"]  = known.confidence
    r["source_url"]  = known.source_url or r["source_url"]
    r["known_exact"] = True

    # Subtype: para chips confirmados/manual que são exceções da família
    # (ex: KMR310001M = LPDDR3, mas família KMR = LPDDR4/4X), usa o subtype
    # salvo no KnownPart em vez do subtype da família.
    # Não afeta outros chips da família — só registros com known.subtype preenchido
    # e confidence=confirmed/manual.
    if human_verified and known.subtype:
        r["subtype"] = known.subtype

    # classification_source reflete qual camada dominou o resultado.
    if grammar_wins:
        r["classification_source"] = "gramática"
    elif r.get("emcp_source") == "gramática+db":
        r["classification_source"] = "gramática+db"
    else:
        r["classification_source"] = "banco de dados"
    return r


# ── Double-check: detecta possível remarked ───────────────────────────────────

def _remarked_summary(r: dict) -> str:
    """
    Formata uma string legível com os valores de capacidade do resultado,
    cobrindo tanto chips standalone (capacity, dram_density) quanto
    eMCP/uMCP (emcp_nand, emcp_ram).

    Usado em remarked_note para que o operador saiba qual campo divergiu.
    Ex: "NAND: eMMC 5.1 64GB · RAM: LPDDR4/4X 4GB"
    """
    parts = []
    if r.get("emcp_nand"):
        parts.append(f"NAND: {r['emcp_nand']}")
    if r.get("emcp_ram"):
        parts.append(f"RAM: {r['emcp_ram']}")
    if r.get("capacity"):
        parts.append(r["capacity"])
    if r.get("dram_density"):
        parts.append(r["dram_density"])
    return " · ".join(parts) if parts else "N/A"


def _extract_gib(text: str) -> float | None:
    """Extrai capacidade em GB a partir de string como '4GB', '512MB'."""
    if not text:
        return None
    m = _CAP_RE.search(text)
    if not m:
        return None
    val, unit = float(m.group(1)), m.group(2).upper()
    if unit == "T":
        return val * 1024  # TB → GB (ex: 1TB = 1024GB)
    if unit == "K":
        return val / 1024 / 1024
    if unit == "M":
        return val / 1024
    return val  # GB


def _check_remarked(grammar_result: dict, db_result: dict) -> bool:
    """
    Retorna True se gramática e banco divergem em capacidade — sinal de possível remarked.
    Só compara campos preenchidos em ambos.

    Compara tanto campos de chip standalone (capacity, dram_density) quanto
    campos de eMCP/uMCP (emcp_nand, emcp_ram) — anteriormente eMCPs eram
    invisíveis para esta função, o que desativava o alerta de remarked para
    a maioria dos chips Samsung no mercado de reciclagem.
    """
    for field in ("capacity", "dram_density", "emcp_nand", "emcp_ram"):
        g_val = grammar_result.get(field)
        d_val = db_result.get(field)
        if not g_val or not d_val:
            continue
        g_cap = _extract_gib(str(g_val))
        d_cap = _extract_gib(str(d_val))
        if g_cap and d_cap and abs(g_cap - d_cap) > 0.1:
            return True
    return False


# ── Helpers de logging ─────────────────────────────────────────────────────────

def _log_search(pn: str, found: bool, source_used: str = ""):
    try:
        SearchLog.objects.create(part_number=pn, found=found, source_used=source_used)
    except Exception:
        logger.exception("Erro ao gravar SearchLog para PN=%s", pn)


def _log_unknown(pn: str):
    try:
        UnknownChip.objects.get_or_create(part_number=pn)
    except Exception:
        logger.exception("Erro ao gravar UnknownChip para PN=%s", pn)


# ── Rentabilidade comercial ────────────────────────────────────────────────────

def _lpddr_generation(text: str) -> int | None:
    """
    Extrai a geração LPDDR como inteiro a partir de uma string de especificação.
        LPDDR / LPDDR (legado)  → 1
        LPDDR2                  → 2
        LPDDR3                  → 3
        LPDDR4 / LPDDR4X / LPDDR4/4X → 4
        LPDDR5 / LPDDR5X        → 5
    Retorna None se não encontrar nenhuma correspondência.

    Usa findall() + max() (espelho de _ddr_generation): quando o chip_type genérico
    "LPDDR" é concatenado ao subtype específico (combined="LPDDR LPDDR4"), o .search()
    pegava o primeiro "LPDDR" (sem número → geração 1) e marcava um LPDDR4/4X como
    LPDDR1 → sucata ERRADA. max() devolve a geração real. (Bug latente exposto pela
    migração da convenção; gen no chip_type genérico envenenava a extração.)
    """
    matches = _LPDDR_GEN_RE.findall(text or "")
    if not matches:
        return None
    gens = [1 if not g else int(g[0]) for g in matches]
    return max(gens)


def _extract_gbit(text: str) -> float | None:
    """
    Extrai valor em Gigabits de strings de densidade DRAM.
    Case-sensitive: "Gb" = Gigabit, "GB" = Gigabyte — não confundir.
    Ex: "8Gb = 1GB por die [✓]" → 8.0
        "2Gb = 256MB por die"   → 2.0
        "1Gb = 128MB por die"   → 1.0
    """
    m = _GBIT_RE.search(text or "")
    if not m:
        return None
    return float(m.group(1))


def _ddr_generation(text: str) -> int | None:
    """
    Extrai a geração DDR (não-LPDDR) como inteiro.
        DDR (sem número) → 1
        DDR2 → 2, DDR3 → 3, DDR4 → 4, DDR5 → 5
    Retorna None se não encontrar.

    Usa findall() + max() para lidar com strings como "DDR DDR3/DDR3L" onde
    chip_type="DDR" e subtype="DDR3/DDR3L" são concatenados em combined.
    search() pegaria o "DDR" genérico primeiro e devolveria geração 1 erroneamente.
    """
    # Verifica LPDDR primeiro: se o texto tem LPDDR, não é DDR standalone
    if _LPDDR_GEN_RE.search(text or ""):
        return None
    matches = _DDR_GEN_RE.findall(text or "")
    if not matches:
        return None
    # findall() com grupo captura a parte numérica (ou "" para DDR sem número)
    gens = [1 if (not g) else int(g[0]) for g in matches]
    return max(gens)


def assess_profitability(result: dict) -> str:
    """
    Avalia a rentabilidade comercial de um chip identificado.

    Retorna:
        "RENTÁVEL"      — chip atende os critérios mínimos de mercado
        "NÃO RENTÁVEL"  — chip abaixo dos critérios mínimos
        "INDETERMINADO" — dados insuficientes para avaliação confiável

    Os limiares são lidos de ProfitabilityConfig (singleton no banco).
    Para alterar as regras sem redeploy: Admin Django → Configuração de Rentabilidade.

    Regras aplicadas (valores default):

        eMCP / uMCP:
            - LPDDR2 ou inferior       → NÃO RENTÁVEL
            - RAM < 1 GB               → NÃO RENTÁVEL
            - NAND < 8 GB              → NÃO RENTÁVEL
            - Todos os critérios OK    → RENTÁVEL

        eMMC standalone:
            - capacidade < 4 GB        → NÃO RENTÁVEL

        UFS standalone:
            - capacidade < 4 GB        → NÃO RENTÁVEL

        LPDDR standalone:
            - LPDDR2 ou inferior       → NÃO RENTÁVEL
            - LPDDR3: < 2 GB           → NÃO RENTÁVEL
            - LPDDR4+: < 1 GB          → NÃO RENTÁVEL

        DDR standalone (threshold em Gigabits por die):
            - DDR2 ou inferior         → NÃO RENTÁVEL
            - DDR3: < 2 Gb (= 256 MB)  → NÃO RENTÁVEL
            - DDR4+: < 1 Gb (= 128 MB)  → NÃO RENTÁVEL

        ePoP (Package on Package, ex.: Samsung KAT):
            → NÃO RENTÁVEL (memória empilhada em SoC — sem mercado B2B de reciclagem)

        NAND Flash raw / NOR Flash / MCP legado:
            → NÃO RENTÁVEL (sucata por tipo, independente de capacidade)

        GDDR standalone (GPU memory):
            - GDDR2 ou inferior       → NÃO RENTÁVEL
            - GDDR3+: sem threshold de densidade definido → INDETERMINADO (raro no fluxo)

        Outros tipos (SoC, SDRAM puro, etc.):
            → INDETERMINADO
    """
    cfg = ProfitabilityConfig.get_config()

    chip_type = (result.get("chip_type") or "").strip()
    subtype   = (result.get("subtype")   or "").strip()
    combined  = f"{chip_type} {subtype}".upper()

    # Despacho pela FONTE ÚNICA (chips/chip_types.py): resolve o token canônico do
    # tipo e a família de rentabilidade. Substitui a SELEÇÃO de branch por substring
    # — os INTERNOS de cada branch (extração de geração/capacidade via `combined`,
    # limiares de ProfitabilityConfig) seguem idênticos. Comportamento preservado,
    # provado pela rede de regressão (docs/PLANO_IMPLEMENTACAO_CONVENCAO.md §3/F3).
    _canon = canonical_chip_type(chip_type, subtype)
    _fam   = profit_family(_canon)

    # ── Tipos sempre NÃO RENTÁVEL (resíduo por tipo, não por capacidade) ─────
    # NAND Flash raw (MT29C, MT29F, K9*): sem controlador eMMC/UFS — resíduo industrial.
    # NOR Flash: memória de código read-only, sem mercado B2B de reciclagem.
    # MCP legado: NAND raw + mDDR1 pré-eMCP, sem liquidez B2B.
    # ePoP (ex.: Samsung KAT): memória empilhada em SoC (Package-on-Package ~2012-2015);
    #   is_emcp=True → sem este guard, entraria no bloco eMCP mas retornaria INDETERMINADO
    #   quando a gramática não decodifica capacidade (placeholder "tipo 'T' — consultar datasheet").
    # is_dead_by_generation() retorna True automaticamente para estes tipos.
    # ⚠ Tipos "dead" agora vêm da FONTE ÚNICA (chips/chip_types.py): nand flash,
    # nor flash, mcp, epop + sdram/rdram/edo dram (anteriores ao DDR1 → sucata).
    # Adicionar um tipo dead = uma entrada no registro, não aqui.
    if _fam == "dead":
        return "NÃO RENTÁVEL"

    # ── eMCP / uMCP ──────────────────────────────────────────────────────────
    # uMCP: mesmas regras do eMCP (NAND ≥ cfg.emcp_min_nand_gb, RAM ≥ cfg.emcp_min_ram_gb).
    # is_emcp cobre ambos via ChipFamily; a checagem explícita do chip_type
    # garante que chip_type="uMCP" (vindo do banco) também seja avaliado.
    if result.get("is_emcp") or _fam == "emcp":
        ram_str  = (result.get("emcp_ram")  or "").strip()
        nand_str = (result.get("emcp_nand") or "").strip()

        # ── FIX 2026-06-26: geração LPDDR no subtype — famílias sem decode map ──
        # Famílias "magras" (sem DecodeMap) têm ram_str="" mas o subtype da ChipFamily
        # pode declarar a geração LPDDR (ex.: subtype="eMCP Toshiba LPDDR2 (legado)").
        # Sem este bloco, o guard abaixo retornaria INDETERMINADO antes de checar a geração,
        # mesmo quando o subtype já é suficiente para decidir NÃO RENTÁVEL por tipo.
        # Chips afetados: TYC* (Toshiba eMCP LPDDR2, sem ChipFamily até 2026-06-26).
        if not ram_str:
            lpddr_gen_sub = _lpddr_generation(combined)
            if lpddr_gen_sub is not None and lpddr_gen_sub < cfg.emcp_min_lpddr_gen:
                return "NÃO RENTÁVEL"

        if not ram_str or not nand_str:
            return "INDETERMINADO"

        # ── FIX 2026-05-27: verificar geração LPDDR ANTES da extração de GB ──
        # LPDDR2 ou inferior → NÃO RENTÁVEL independente da capacidade numérica.
        # Caso típico: emcp_ram="LPDDR2" (sem GB) → _extract_gib retornaria None
        # e causaria retorno INDETERMINADO antes de checar a geração (bug original).
        # Chips afetados: KMN5X000ZM, KML7X000HM, KMK*, KMV* etc. (campos sem GB).
        lpddr_gen = _lpddr_generation(ram_str)
        if lpddr_gen is not None and lpddr_gen < cfg.emcp_min_lpddr_gen:
            return "NÃO RENTÁVEL"

        ram_gb  = _extract_gib(ram_str)
        nand_gb = _extract_gib(nand_str)

        if ram_gb is None or nand_gb is None:
            return "INDETERMINADO"

        if lpddr_gen is None:
            return "INDETERMINADO"

        if lpddr_gen < cfg.emcp_min_lpddr_gen:  # redundante pós-fix, mantido por segurança
            return "NÃO RENTÁVEL"
        if ram_gb < cfg.emcp_min_ram_gb - 0.01:
            return "NÃO RENTÁVEL"
        if nand_gb < cfg.emcp_min_nand_gb - 0.01:
            return "NÃO RENTÁVEL"
        return "RENTÁVEL"

    # ── eMMC standalone ──────────────────────────────────────────────────────
    if _fam == "emmc":
        cap_gb = _extract_gib(result.get("capacity") or "")
        if cap_gb is None:
            return "INDETERMINADO"
        return "RENTÁVEL" if cap_gb >= cfg.emmc_min_cap_gb - 0.01 else "NÃO RENTÁVEL"

    # ── UFS standalone ────────────────────────────────────────────────────────
    if _fam == "ufs":
        cap_gb = _extract_gib(result.get("capacity") or "")
        if cap_gb is None:
            return "INDETERMINADO"
        return "RENTÁVEL" if cap_gb >= cfg.ufs_min_cap_gb - 0.01 else "NÃO RENTÁVEL"

    # ── LPDDR standalone ─────────────────────────────────────────────────────
    if _fam == "lpddr":
        lpddr_gen = _lpddr_generation(combined)
        if lpddr_gen is None:
            return "INDETERMINADO"
        # ── FIX 2026-06-19: verificar geração ANTES da extração de GB ────────
        # Espelho do fix eMCP 2026-05-27. LPDDR2 ou inferior → NÃO RENTÁVEL
        # independente da capacidade numérica.
        # Caso típico: dram_density="8Gb = 1GB por die [~]" → _strip_capacity
        # remove "8Gb" e "1GB" (re.I) → cap_gb fica None → retornava INDETERMINADO
        # antes de checar geração → is_dead_by_generation=False → chip LPDDR2
        # caía na FILA (PendingEntry) em vez do descarte automático.
        # Chips afetados: K3PE, K4P, K4E8E e qualquer LPDDR2 com decode DRAM_MOBILE.
        if lpddr_gen < cfg.lpddr_min_gen:
            return "NÃO RENTÁVEL"
        cap_gb = _extract_gib(result.get("capacity") or result.get("dram_density") or "")
        if cap_gb is None:
            return "INDETERMINADO"
        # LPDDR4+ e LPDDR3 têm limiares separados
        threshold_gb = cfg.lpddr4plus_min_cap_gb if lpddr_gen >= 4 else cfg.lpddr3_min_cap_gb
        if cap_gb < threshold_gb - 0.01:
            return "NÃO RENTÁVEL"
        return "RENTÁVEL"

    # ── GDDR (memória de GPU) ─────────────────────────────────────────────────
    # "DDR" in combined é True para "GDDR2" (substring) → o bloco DDR abaixo seria
    # atingido, mas _ddr_generation usa (?<![A-Z])DDR: lookbehind falha em "GDDR2"
    # (G precede DDR) → ddr_gen=None → INDETERMINADO. Solução: bloco GDDR próprio
    # verificado ANTES do DDR para interceptar e tratar corretamente.
    # GDDR2 e abaixo (ou sem número de geração): NÃO RENTÁVEL.
    # GDDR3+: raro no fluxo — sem threshold de densidade definido → INDETERMINADO.
    if _fam == "gddr":
        m = re.search(r'GDDR(\d+)', combined)
        gddr_gen = int(m.group(1)) if m else None
        if gddr_gen is None or gddr_gen < cfg.gddr_min_gen:
            return "NÃO RENTÁVEL"
        return "INDETERMINADO"

    # ── DDR standalone ────────────────────────────────────────────────────────
    # Threshold em Gigabits (não Gigabytes): DDR3 ≥ cfg.ddr3_min_gbit; DDR4+ ≥ cfg.ddr4plus_min_gbit.
    #   2Gb = 256MB | 4Gb = 512MB | 8Gb = 1GB
    # Fonte primária: dram_density ("8Gb = 1GB por die [✓]") → extrai Gigabits.
    # Fallback: capacity em GB (KnownParts enriquecidos).
    if _fam == "ddr":
        ddr_gen = _ddr_generation(combined)
        if ddr_gen is None:
            return "INDETERMINADO"
        if ddr_gen < cfg.ddr_min_gen:
            return "NÃO RENTÁVEL"
        # DDR4+ e DDR3 têm limiares de densidade separados (em Gigabits)
        min_gbit   = cfg.ddr4plus_min_gbit if ddr_gen >= 4 else cfg.ddr3_min_gbit
        # Fallback em GB: 1 Gb = 0.125 GB
        min_cap_gb = min_gbit * 0.125
        gbit = _extract_gbit(result.get("dram_density") or "")
        if gbit is not None:
            return "RENTÁVEL" if gbit >= min_gbit - 0.01 else "NÃO RENTÁVEL"
        cap_gb = _extract_gib(result.get("capacity") or "")
        if cap_gb is None:
            return "INDETERMINADO"
        return "RENTÁVEL" if cap_gb >= min_cap_gb - 0.01 else "NÃO RENTÁVEL"

    # Tipo não coberto pelas regras (SoC, SDRAM puro, etc.)
    return "INDETERMINADO"


# Números de capacidade/densidade (ex.: "16GB", "1.5GB", "512MB", "8Gb", "1TB").
# TB adicionado 2026-06-26 para suportar UFS 1TB+ (Kioxia THGJF*).
_CAP_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:TB|GB|MB)\b", re.I)


def _strip_capacity(result: dict) -> dict:
    """Cópia de `result` com os NÚMEROS de capacidade/densidade removidos,
    preservando tipo, geração e subtype. Ex.: "LPDDR3 1GB" → "LPDDR3"; "16GB" → "".
    Base para detectar não-rentabilidade que INDEPENDE da capacidade."""
    out = dict(result)
    for k in ("capacity", "dram_density", "emcp_ram", "emcp_nand"):
        v = out.get(k)
        if v:
            out[k] = _CAP_NUM_RE.sub("", str(v)).strip()
    return out


def is_dead_by_generation(result: dict) -> bool:
    """
    True quando o chip é NÃO RENTÁVEL por um motivo que **independe da capacidade**
    (geração / era de tecnologia) — em oposição a "não rentável por capacidade
    pequena".

    DERIVADO de assess_profitability (FONTE ÚNICA da verdade): removemos os números
    de capacidade do `result` e perguntamos se ele AINDA é NÃO RENTÁVEL. Se sim, a
    rejeição não dependia da capacidade → é por geração/era.

    Por que derivar (e não manter uma lista própria): fica SEMPRE em sincronia com
    as regras de rentabilidade. Qualquer regra capacity-independent nova lá
    (LPDDR2-, DDR2-, MCP legado, NOR Flash/K5, …) passa a valer aqui
    automaticamente — sem um segundo sistema para manter e sair de sincronia.

    Usado pelo gateway do estoque: chip morto por geração vai direto ao descarte
    mesmo SEM confirmação no banco e SEM capacidade mapeada (rótulo distinto +
    auditoria). Capacidade pequena NÃO entra aqui — essa exige confirmação.
    """
    return assess_profitability(_strip_capacity(result)) == "NÃO RENTÁVEL"


# ── Ponto de entrada público ───────────────────────────────────────────────────

def _pick_best_known(candidates: list):
    """Dentre KnownParts com o mesmo part_number_norm, escolhe o melhor: chip_type
    preenchido > escada de confiança (confirmed>manual>distributor>estimated) > mais
    recente. (Pós-dedupe da parte 2 há sempre ≤1; aqui resolve as colisões cruas
    restantes sem o antigo 'salta silencioso' do MultipleObjectsReturned.)"""
    _rank = {"confirmed": 3, "manual": 2, "distributor": 1, "estimated": 0}
    return max(candidates, key=lambda k: (
        bool(k.chip_type),
        _rank.get(k.confidence, -1),
        k.last_updated or k.added_at,
    ))


def classify(pn_raw: str) -> dict:
    """
    Classifica um Part Number.

    Fluxo:
      1. Banco exato (confirmados) → resultado completo e verificado
      2. Gramática da família      → decodificação posicional do PN
      3. Fuzzy matching            → sugestões de digitação (PN desconhecido)
    """
    pn = normalize_pn(pn_raw)

    if not pn:
        return {"pn": pn_raw, "known": False, "error": "PN inválido"}

    # ── Detecta PN potencialmente truncado ──────────────────────────────────
    # Se a família tem pn_length definido e o PN digitado é mais curto, tratamos
    # como "possivelmente truncado": usado adiante para avisar o operador (campo
    # pn_incomplete) quando a gramática também não decodifica a capacidade.
    # Nota: pn_short != pn_incomplete. Um PN pode ser curto mas a gramática já
    # retornar resultado completo (ex: KLMCGUCTA/9 chars: capacidade em pn[3]).
    # O aviso visual só aparece quando o resultado da gramática também for parcial.
    fam_early = _match_family(pn)
    pn_short = bool(
        fam_early and fam_early.pn_length and len(pn) < fam_early.pn_length
    )

    # ── 1. Busca exata no banco (confirmados) ────────────────────────────────
    # Registros UTILIZÁVEIS (com specs reais OU confirmados) — gate fiel ao antigo
    # status="enriched". Distribuidor/estimado COM capacidade voltam a ser
    # reconhecidos aqui (known_exact=True); a precedência segue em _result_from_known
    # (só confirmed/manual vencem a gramática completa). Busca EXATA por part_number
    # (BUG-8: cobre PNs sem sufixo de package, ex: H9HP16AECMMD).
    _db_qs = (
        KnownPart.objects
        .filter(_USABLE)
        .select_related("family", "brand", "family__doc_page")
    )
    if pn_short:
        # PN truncado (operador ainda digitando / sufixo de lote): aceita só
        # confirmados (BUG-8) — evita casar registro de baixa confiança por
        # part_number exato enquanto a entrada está incompleta.
        _db_qs = _db_qs.filter(confidence__in=_CONFIRMED_CONFIDENCE)
    try:
        known = _db_qs.get(part_number=pn)
        # Preferir ChipFamily pelo prefixo — mais confiável que o chip_type
        # salvo no registro (que pode estar errado, ex: uMCP rotulado como eMCP).
        fam = _match_family(pn) or known.family
        if fam:
            result = _result_from_known(pn, known, fam)
        else:
            result = {
                "pn":           pn,
                "known":        True,
                "known_exact":  True,
                "chip_type":    known.chip_type,
                "subtype":      known.subtype,
                "brand":        known.brand.name,
                "capacity":     _clean(known.capacity),
                "emcp_ram":     _clean(known.emcp_ram),
                "emcp_nand":    _clean(known.emcp_nand),
                "device":       known.device,
                "confidence":   known.confidence,
                "source_url":   known.source_url,
                "is_emcp":      bool(known.emcp_ram),
                "tip":          known.notes or "",
                "reasoning":    [],
                "from_web":     False,
                "doc_url":      None,
                "remarked_flag":     False,
                "fuzzy_suggestions": [],
                "interface":         known.interface,
                "family_prefix":     "",
                # Sem família não há como saber se é não documentada — assume False.
                "family_undocumented": False,
            }
        result["profitable"] = assess_profitability(result)
        _log_search(pn, found=True, source_used="db_exact")
        return result
    except KnownPart.DoesNotExist:
        pass

    # ── 1a′. Fallback por part_number_norm (passo 1A) ───────────────────────
    # A busca exata por part_number falha para registros salvos COM separador
    # (`-`/espaço/`:`/`.`). A coluna `part_number_norm` (normalize_pn no write-time)
    # casa todos de uma vez, sem o Replace em runtime — e sem o bug dos `:`/`.` que
    # deixava ~1908 PNs em "tipo vazio" na bancada. Pode haver >1 candidato enquanto
    # as duplicatas não forem deduplicadas (parte 2): escolhe o melhor por
    # _pick_best_known (chip_type preenchido > confiança > mais recente).
    _norm_candidates = list(_db_qs.filter(part_number_norm=pn))
    if _norm_candidates:
        known = _pick_best_known(_norm_candidates)
        fam = _match_family(pn) or known.family
        if fam:
            result = _result_from_known(pn, known, fam)
        else:
            result = {
                "pn":           pn,
                "known":        True,
                "known_exact":  True,
                "chip_type":    known.chip_type,
                "subtype":      known.subtype,
                "brand":        known.brand.name,
                "capacity":     _clean(known.capacity),
                "emcp_ram":     _clean(known.emcp_ram),
                "emcp_nand":    _clean(known.emcp_nand),
                "device":       known.device,
                "confidence":   known.confidence,
                "source_url":   known.source_url,
                "is_emcp":      bool(known.emcp_ram),
                "tip":          known.notes or "",
                "reasoning":    [],
                "from_web":     False,
                "doc_url":      None,
                "remarked_flag":     False,
                "fuzzy_suggestions": [],
                "interface":         known.interface,
                "family_prefix":     "",
                "family_undocumented": False,
            }
        result["profitable"] = assess_profitability(result)
        _log_search(pn, found=True, source_used="db_exact")
        return result

    # ── 1b. FBGA lookup ─────────────────────────────────────────────────────
    # Código FBGA (ex: D9VFC) gravado a laser no chip pela Micron.
    # O operador na esteira digita o código de 5 chars que vê no chip —
    # não o PN completo. Padrão: [A-Z]\d[A-Z0-9]{3} (D9XXX, D8XXX, etc.).
    #
    # Se estiver cadastrado em KnownPart.fbga_code → retorna o resultado enriquecido.
    # Se não estiver → registra no UnknownChip com nota "FBGA desconhecido"
    # para o job noturno processar via micron.com/fbga-parts-decoder.
    #
    # Este bloco corre ANTES da gramática porque um FBGA code nunca vai bater
    # em nenhum prefixo de família (prefixos são MT53B, MTFC, etc.) — cair na
    # gramática seria apenas desperdício de CPU + risco de resultado incorreto.
    if _FBGA_RE.match(pn):
        try:
            known_fbga = KnownPart.objects.filter(
                _USABLE
            ).select_related(
                "family", "brand", "family__doc_page"
            ).get(fbga_code=pn)
            fam_fbga = _match_family(known_fbga.part_number) or known_fbga.family
            if fam_fbga:
                result = _result_from_known(known_fbga.part_number, known_fbga, fam_fbga)
            else:
                result = {
                    "pn":            known_fbga.part_number,
                    "known":         True,
                    "known_exact":   True,
                    "chip_type":     known_fbga.chip_type,
                    "subtype":       known_fbga.subtype,
                    "brand":         known_fbga.brand.name,
                    "capacity":      _clean(known_fbga.capacity),
                    "emcp_ram":      _clean(known_fbga.emcp_ram),
                    "emcp_nand":     _clean(known_fbga.emcp_nand),
                    "device":        known_fbga.device,
                    "confidence":    known_fbga.confidence,
                    "source_url":    known_fbga.source_url,
                    "is_emcp":       bool(known_fbga.emcp_ram),
                    "tip":           known_fbga.notes or "",
                    "reasoning":     [],
                    "from_web":      False,
                    "doc_url":       None,
                    "remarked_flag":      False,
                    "fuzzy_suggestions":  [],
                    "interface":          known_fbga.interface,
                    "family_prefix":      "",
                    "family_undocumented": False,
                    # Lê density_gbit/density_gb do KnownPart — preenchidos pelo
                    # import_micron_catalog. Sem família não há decode posicional,
                    # então esses campos são a única fonte de densidade.
                    "dram_density":       (
                        f"{known_fbga.density_gbit} = {known_fbga.density_gb} por die [✓]"
                        if known_fbga.density_gbit and known_fbga.density_gb else
                        f"{known_fbga.density_gbit} por die [✓]"
                        if known_fbga.density_gbit else None
                    ),
                    "suffix_note":        None,
                }
            # Expõe o PN completo separado do código FBGA digitado
            result["fbga_input"]  = pn
            result["pn_full"]     = known_fbga.part_number
            result["profitable"]  = assess_profitability(result)
            _log_search(pn_raw, found=True, source_used="db_fbga")
            return result
        except KnownPart.MultipleObjectsReturned:
            # Múltiplos KnownParts com o mesmo fbga_code.
            # Situação anômala: pode ocorrer quando enrich_micron_fbga salva o PN
            # no formato raw da API (ex: "MT29C4G48MAZAPAKD-5 IT") e depois
            # fix_known_parts cria o PN normalizado (ex: "MT29C4G48MAZAPAKD5IT") —
            # dois registros, mesmo fbga_code.
            # Estratégia: preferir registros com chip_type preenchido (registros
            # normalizados pelo fix_known_parts); só usar o "vazio" se todos forem vazios.
            logger.warning("FBGA ambíguo: múltiplos KnownParts com fbga_code=%s — preferindo chip_type preenchido", pn)
            _fbga_qs = KnownPart.objects.filter(
                _USABLE, fbga_code=pn
            ).select_related("family", "brand", "family__doc_page")
            known_fbga = _fbga_qs.exclude(chip_type="").first() or _fbga_qs.first()
            if known_fbga:
                fam_fbga = _match_family(known_fbga.part_number) or known_fbga.family
                result = _result_from_known(known_fbga.part_number, known_fbga, fam_fbga) if fam_fbga else {
                    "pn": known_fbga.part_number, "known": True, "known_exact": True,
                    "chip_type": known_fbga.chip_type, "subtype": known_fbga.subtype,
                    "brand": known_fbga.brand.name, "capacity": _clean(known_fbga.capacity),
                    "emcp_ram": _clean(known_fbga.emcp_ram), "emcp_nand": _clean(known_fbga.emcp_nand),
                    "device": known_fbga.device, "confidence": known_fbga.confidence,
                    "source_url": known_fbga.source_url, "is_emcp": bool(known_fbga.emcp_ram),
                    "tip": known_fbga.notes or "", "reasoning": [], "from_web": False,
                    "doc_url": None, "remarked_flag": False, "fuzzy_suggestions": [],
                    "interface": known_fbga.interface, "family_prefix": "",
                    "family_undocumented": False, "suffix_note": None,
                    "dram_density": (
                        f"{known_fbga.density_gbit} = {known_fbga.density_gb} por die [✓]"
                        if known_fbga.density_gbit and known_fbga.density_gb else
                        f"{known_fbga.density_gbit} por die [✓]"
                        if known_fbga.density_gbit else None
                    ),
                }
                result["fbga_input"] = pn
                result["pn_full"]    = known_fbga.part_number
                result["profitable"] = assess_profitability(result)
                _log_search(pn_raw, found=True, source_used="db_fbga")
                return result
            # Nenhum enriched encontrado — cai no fluxo de desconhecido abaixo
        except KnownPart.DoesNotExist:
            # FBGA não cadastrado → enfileira para enriquecimento noturno
            try:
                UnknownChip.objects.get_or_create(
                    part_number=pn,
                    defaults={"notes": "FBGA code — pendente resolução noturna via micron.com/fbga-parts-decoder"},
                )
            except Exception:
                logger.exception("Erro ao registrar FBGA desconhecido PN=%s", pn)
            _log_search(pn_raw, found=False, source_used="fbga_unknown")
            # Busca FBGAs próximos para ajudar o operador a corrigir o código.
            # Confusões visuais comuns: O/0, Q/0, B/8, M/W — distância ≤ 2 captura
            # praticamente todos os erros de 1 caractere nesse espaço de 5 chars.
            fbga_fuzzy = _fuzzy_fbga_candidates(pn)
            return {
                "pn":              pn,
                "known":           False,
                "fbga_input":      pn,
                "fbga_unknown":    True,
                "fuzzy_suggestions": fbga_fuzzy,
                "in_review_queue": True,
            }

    # ── 2. Gramática da família ──────────────────────────────────────────────
    fam = fam_early  # já resolvido acima, reutiliza sem novo SELECT
    if fam:
        grammar_result = _result_from_family(pn, fam)

        # Calcula completude real da gramática (independente de pn_short)
        _grammar_emcp_ok = fam.is_emcp and bool(
            _CAP_RE.search(str(grammar_result.get("emcp_ram")  or "")) and
            _CAP_RE.search(str(grammar_result.get("emcp_nand") or ""))
        )
        _grammar_cap_ok = (not fam.is_emcp) and bool(
            _CAP_RE.search(str(grammar_result.get("capacity") or grammar_result.get("dram_density") or ""))
        )
        grammar_complete = _grammar_emcp_ok or _grammar_cap_ok

        # pn_incomplete = PN está curto E gramática não conseguiu decodificar a
        # capacidade. Se a gramática retornou resultado completo mesmo com PN curto
        # (ex: KLM com capacidade em pn[3]), não há motivo para avisar o operador.
        pn_incomplete = pn_short and not grammar_complete
        if pn_incomplete:
            grammar_result["pn_incomplete"]       = True
            grammar_result["pn_length_expected"]  = fam.pn_length

        # Sem Gemini: a gramática é o resultado final da camada 2. PNs que a
        # gramática não decodifica por completo permanecem parciais — o operador
        # confirma manualmente, alimentando populate_*/import_*/fix_*.

        # Double-check de chip remarked: se já existe um KnownPart para este PN
        # (confirmados retornaram na camada 1, então aqui é registro NÃO confirmado
        # — ex.: histórico de distribuidor) e a capacidade diverge da gramática,
        # sinaliza possível remarcação — pista crítica no mercado de reciclagem.
        try:
            db_part = KnownPart.objects.get(part_number=pn)
            if db_part.family:
                db_result = _result_from_known(pn, db_part, db_part.family)
                if _check_remarked(grammar_result, db_result):
                    grammar_result["remarked_flag"] = True
                    # BUG-1: _remarked_summary() cobre emcp_nand/emcp_ram também
                    # (capacity/dram_density são None para eMCP/uMCP).
                    grammar_result["remarked_note"] = (
                        f"⚠️ Atenção: gramática indica "
                        f"{_remarked_summary(grammar_result)}, "
                        f"banco indica "
                        f"{_remarked_summary(db_result)}. "
                        f"Verificar possível chip remarked."
                    )
        except KnownPart.DoesNotExist:
            pass

        # Sem fila de revisão: o antigo KnownPart status="raw" (criado a cada busca
        # de PN não confirmado) foi removido junto com o campo status. PNs buscados
        # ficam rastreados em SearchLog; PNs que o operador tenta lançar e não são
        # confirmados vão para a fila de conferência do estoque (PendingEntry). O
        # banco confirmado cresce só via populate_*/import_*/fix_* + aprovação no admin.
        grammar_result["grammar_complete"]  = grammar_complete
        grammar_result["in_review_queue"]   = False
        grammar_result["profitable"] = assess_profitability(grammar_result)

        # Flag explícita de "não confirmado no banco" → aviso visual para o operador
        # conferir a digitação. Chegamos à camada 2, logo a busca exata de
        # confirmados (camada 1) falhou: este PN não está confirmado no banco.
        grammar_result["pn_not_in_db"] = True

        # ── Approach 2: sugestões em gramática sem match exato ───────────────
        # Combina prefixo (PN incompleto) + fuzzy visual (typo).
        # Ex: H5TQ2G83 → H5TQ2G83CFR (prefixo) ou KMQ3100068 → KMQ310006B (fuzzy).
        if grammar_result["pn_not_in_db"] or grammar_result.get("pn_incomplete"):
            suggs = _combined_suggestions(pn)
            if suggs:
                grammar_result["fuzzy_suggestions"] = suggs

        _log_search(pn, found=True, source_used="grammar")
        return grammar_result

    # ── 3. Prefixo desconhecido → sugestões (prefixo + fuzzy) ────────────────
    # Nenhuma família bateu o prefixo: fabricante não catalogado ou leitura
    # incorreta do PN. Loga em UnknownChip e oferece sugestões — prefixo (PN
    # incompleto) primeiro, fuzzy visual (typo) depois — para o operador corrigir.
    _log_unknown(pn)
    suggs = _combined_suggestions(pn)
    _log_search(pn, found=False, source_used="not_found")

    return {
        "pn":               pn,
        "known":            False,
        "fuzzy_suggestions": suggs,
        "in_review_queue":  True,   # UnknownChip já logado por _log_unknown()
    }
