"""
WhatTheChip — Engine de Classificação de Chips
===============================================
Classifica um Part Number em quatro camadas:

  1. Banco exato (KnownPart enriched)  → resultado completo e verificado
  2. Gramática da família (ChipFamily) → decodificação posicional do PN
       └→ resultado sempre enfileirado para revisão manual (KnownPart raw)
         se o PN não estiver já no banco principal
  3. Gemini puro (prefix desconhecido) → fallback IA com Google Search grounding
         (somente quando settings.GEMINI_ENABLED = True)
  4. Fuzzy matching                    → sugestões para erros de digitação

Fila de revisão (Camada 2):
    Todo PN que não está no banco principal (status=enriched) é enfileirado
    automaticamente como KnownPart(status=raw) após a classificação.
    O banco principal cresce apenas via revisão manual ou comandos de gestão.
    Nunca auto-promove entradas para enriched a partir de input de usuário.

Gemini:
    Controlado pelo flag settings.GEMINI_ENABLED (padrão: False).
    Para reativar: defina GEMINI_ENABLED=true no .env e reinicie o servidor.
    O script scripts/enrich_gemini.py é independente deste flag.

Double-check:
    Quando o banco E a gramática têm resultados, eles são comparados.
    Divergência de capacidade é sinalizada como possível chip remarked.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from functools import lru_cache

logger = logging.getLogger(__name__)

from django.db.models.functions import Length

from .models import Brand, ChipFamily, DecodeMap, KnownPart, SearchLog, Source, UnknownChip


# ── Fuzzy matching ─────────────────────────────────────────────────────────────

COMMON_CONFUSIONS = [
    ("O", "0"), ("I", "1"), ("B", "8"), ("V", "Y"), ("Z", "2"), ("S", "5"),
]


def _edit_distance(a: str, b: str) -> int:
    """Distância de Levenshtein."""
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


def _fuzzy_candidates(pn: str, threshold: int = 2) -> list:
    """Retorna KnownParts parecidos por distância de edição."""
    all_parts = KnownPart.objects.filter(status="enriched").values_list("part_number", flat=True)
    matches = []
    for candidate in all_parts:
        if abs(len(candidate) - len(pn)) > threshold:
            continue
        dist = _edit_distance(pn, candidate)
        if dist <= threshold:
            matches.append((dist, candidate))
    matches.sort()
    top_pns = [c for _, c in matches[:5]]
    if not top_pns:
        return []
    # BUG-5: substituído N+1 get() individuais por um único filter com select_related.
    parts_by_pn = {
        p.part_number: p
        for p in KnownPart.objects.filter(part_number__in=top_pns).select_related("brand", "family")
    }
    return [parts_by_pn[c] for _, c in matches[:5] if c in parts_by_pn]


# ── Mapa de decodificação ──────────────────────────────────────────────────────
#
# lru_cache: os mapas de decodificação (SAM_EMCP_CAP, SAM_EMCP_GEN, etc.) mudam
# só quando populate_samsung é executado. Cache em memória elimina um SELECT por
# mapa por classificação. Limpar com _load_decode_map.cache_clear() após populate.

@lru_cache(maxsize=None)
def _load_decode_map(map_name: str) -> dict:
    rows = DecodeMap.objects.filter(map_name=map_name).values("char_key", "val_primary", "val_secondary")
    return {r["char_key"]: (r["val_primary"], r["val_secondary"]) for r in rows}


# ── Match de família ──────────────────────────────────────────────────────────
#
# lru_cache: ChipFamily muda só em operações administrativas (populate_samsung,
# admin). Cache elimina SELECT + iteração Python em todo classify(). A lista é
# carregada uma vez e reutilizada enquanto o processo estiver ativo.
# Limpar com _get_all_families.cache_clear() após alterações no banco.

@lru_cache(maxsize=1)
def _get_all_families() -> list:
    """Carrega todas as famílias ativas, ordenadas por prioridade e comprimento."""
    return list(
        ChipFamily.objects
        .filter(active=True)
        .annotate(prefix_len=Length("prefix"))
        .order_by("priority", "-prefix_len")
        .select_related("doc_page")
    )


def _match_family(pn: str):
    """Retorna ChipFamily com o prefixo mais longo que bater no PN."""
    for fam in _get_all_families():
        if pn.startswith(fam.prefix):
            return fam
    return None


def clear_engine_cache():
    """Invalida os caches em memória do engine. Chamar após populate_samsung."""
    _load_decode_map.cache_clear()
    _get_all_families.cache_clear()


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
_CAP_RE = re.compile(r"(\d+)\s*([GMK])B", re.I)


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
        "confidence":    "estimated",
        "source_url":    None,
        "from_web":      False,
        "suffix_note":   None,
        "remarked_flag": False,
        "fuzzy_suggestions": [],
        "classification_source": "gramática",
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

        # Versão NAND eMMC: usa fam.interface se preenchido (ex: "eMMC 5.1")
        nand_version = fam.interface or "eMMC"

        # Monta strings finais
        if _nand_cap:
            r["emcp_nand"] = f"{nand_version} {_nand_cap}".strip()
        else:
            r["emcp_nand"] = nand_version  # parcial, Gemini vai completar

        if _ram_cap:
            r["emcp_ram"] = f"{ram_type} {_ram_cap}".strip()
        else:
            r["emcp_ram"] = ram_type       # parcial, Gemini vai completar

        # Considera decode completo se:
        #   - NAND via decode_cap_map E RAM via val_secondary (padrão Samsung), OU
        #   - NAND via decode_cap_map E RAM via decode_gen_map com capacidade embutida
        #     (padrão SK Hynix: "LPDDR3 4GB" vem do gen map, _ram_cap é None).
        _ram_from_gen = _decoded_gen and bool(_CAP_RE.search(_decoded_gen))
        r["emcp_source"] = "gramática" if (_nand_cap and (_ram_cap or _ram_from_gen)) else "parcial (gramática)"

        # interface já está codificada em emcp_nand (ex: "eMMC 5.1 64GB").
        # Exibi-la separadamente causaria redundância/confusão na UI ("Interface: LPDDR+eMMC").
        r["interface"] = ""

    # ── Densidade DRAM ───────────────────────────────────────────────────────
    if fam.decode_density_type and not fam.is_emcp:
        dtype = fam.decode_density_type
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

    # Verifica se a gramática produziu resultado completo (sem precisar de Gemini)
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
            # EXCEÇÃO DE TIPO RAM: quando a família tem decode_gen_map configurado,
            # o tipo RAM decodificado pela gramática (ex: "LPDDR4/4X" para KMR) é
            # SEMPRE preferido sobre o valor armazenado no DB — mesmo que o DB tenha
            # a capacidade correta. Isso evita que valores de AI desatualizados
            # (ex: "LPDDR3" salvo antes de corrigirmos o bug do R=LPDDR4/4X) sobrevivam
            # indefinidamente no banco sem re-enriquecimento manual.
            grammar_ram = r.get("emcp_ram") or ""
            if fam.decode_gen_map and grammar_ram and not _CAP_RE.search(grammar_ram):
                # Gramática tem o TIPO mas não a capacidade (cap_key ausente do mapa).
                # Complementa com a capacidade que o DB já tem.
                db_ram = _clean(known.emcp_ram) or ""
                cap_match = _CAP_RE.search(db_ram)
                if cap_match:
                    r["emcp_ram"]    = f"{grammar_ram} {cap_match.group(0)}"
                    r["emcp_source"] = "gramática+db"
                else:
                    # DB também não tem capacidade — deixa o tipo parcial
                    r["emcp_source"] = "gramática (cap. não mapeada)"
            else:
                # DB vence na capacidade. Mas o TIPO RAM (LPDDR4X, LPDDR5…) é
                # definido pela família — não por catálogo de distribuidor.
                # Se decode_gen_map está configurado, o tipo da gramática sempre
                # prevalece; apenas a capacidade numérica vem do DB.
                db_ram = _clean(known.emcp_ram) or ""
                if fam.decode_gen_map and grammar_ram:
                    grammar_type = grammar_ram.split()[0]   # ex: "LPDDR4X"
                    cap_match    = _CAP_RE.search(db_ram)
                    if cap_match and grammar_type:
                        r["emcp_ram"] = f"{grammar_type} {cap_match.group(0)}"
                    else:
                        r["emcp_ram"] = db_ram or r["emcp_ram"]
                else:
                    r["emcp_ram"] = db_ram or r["emcp_ram"]
                r["emcp_source"] = known.confidence

            # NAND: a interface física (UFS vs eMMC) é definida pela família,
            # não pelo banco de dados. Distribuidores frequentemente preenchem
            # "eMMC" para chips uMCP UFS por copy-paste de catálogo genérico.
            db_nand = _clean(known.emcp_nand) or ""
            if db_nand:
                if fam.interface and "UFS" in fam.interface and "eMMC" in db_nand:
                    # BUG-2: Família é UFS mas DB diz "eMMC" → corrige o rótulo
                    # preservando apenas a capacidade numérica.
                    # Antes: db_nand.replace("eMMC", fam.interface.split()[0])
                    #   → perdia a versão ("UFS 3.1" virava "UFS") ou gerava
                    #   versão errada ("UFS 5.1 32GB" quando DB tinha "eMMC 5.1 32GB").
                    # Agora: extrai o número de capacidade e reconstrói com interface completa.
                    _nand_cap_match = _CAP_RE.search(db_nand)
                    if _nand_cap_match:
                        r["emcp_nand"] = f"{fam.interface} {_nand_cap_match.group(0)}"
                    else:
                        r["emcp_nand"] = fam.interface  # sem capacidade: ao menos corrige interface
                else:
                    r["emcp_nand"] = db_nand
            # (se db_nand vazio, mantém o valor da gramática)
        r["emcp_device"] = known.device or None
        r["source_url"]  = known.source_url
    else:
        if not grammar_wins:
            if known.capacity:
                r["capacity"] = _clean(known.capacity)
            if known.density_gbit:
                r["dram_density"] = f"{known.density_gbit} = {known.density_gb} por die [✓]"
        if known.device:
            r["device"] = known.device

    r["confidence"]  = known.confidence
    r["source_url"]  = known.source_url or r["source_url"]
    r["known_exact"] = True
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


# ── Gemini fallback ────────────────────────────────────────────────────────────

GEMINI_PROMPT = """Você é especialista em chips de memória e semicondutores para dispositivos eletrônicos.
Pesquise o Part Number abaixo — use o Google Search se disponível.

Part Number: {pn}
{family_hint}
⚠ REGRA CRÍTICA PARA eMCP/uMCP:
Identificar apenas que o chip É um eMCP NÃO É SUFICIENTE.
Para chips eMCP e uMCP, os campos "ram" e "nand" são OBRIGATÓRIOS com valores reais (ex: "LPDDR4X 4GB", "eMMC 5.1 64GB").
Se você encontrar que é um eMCP mas não tem os valores de RAM e NAND, CONTINUE pesquisando.
Busque em: preduo.com, censtry.com, serviceemmc.com, jotrin.com, wolfchip.com, glochip.com

== GUIA DE DECODIFICAÇÃO DE PART NUMBERS ==

SAMSUNG eMCP (KMR, KMQ, KMD, KMF, KMK, KMG, KM3, KM5, KM8...):
  Prefixo KM = eMCP Samsung (NAND eMMC + LPDDR RAM no mesmo package)
  Prefixo KLM = eMMC Samsung (standalone, sem RAM)
  Para KLM: Pos 3 = capacidade NAND (A=4GB, B=8GB, C=16GB, D=32GB, E=64GB, F=128GB, G=256GB)

SK HYNIX eMCP (H9TQ, H9HP, H9HQ):
  H9TQ = eMCP (eMMC + LPDDR). Buscar capacidade exata em preduo.com ou glochip.com.

MICRON eMCP (MTFC, MT29):
  MTFC = eMMC Micron. MT29 + prefixo específico pode ser eMCP.

NANYA DRAM (NT5, NT5C, NT5CC, NT6):
  NT5CC256M16 = DDR3L — 256M×16bit = 4Gbit = 512MB por die
  Regra: (número_M × bits_bus) / 8 = MB por die

QUALCOMM SoC (SM, MSM, APQ, SDM): SM8xxx=Snapdragon 8xx, SM6xxx=6xx
MEDIATEK SoC (MT6, MT8): MT6xxx=Helio/Dimensity, MT8xxx=tablet
GIGADEVICE NOR (GD25): GD25Q128=128Mbit=16MB

Responda APENAS com JSON válido (sem markdown):
{{
  "brand": "nome da marca",
  "chip_type": "tipo do chip",
  "ram": null,
  "nand": null,
  "capacity": null,
  "interface": null,
  "device": null,
  "source_url": null,
  "confidence": "high|medium|low",
  "reasoning": "de onde vieram os dados"
}}

- ram:      eMCP/uMCP APENAS — tipo + capacidade. Ex: "LPDDR4X 4GB"
- nand:     eMCP/uMCP APENAS — versão + capacidade. Ex: "eMMC 5.1 32GB"
- capacity: eMMC/UFS/DRAM standalone. Ex: "64GB", "512MB"
- chip_type: eMCP | uMCP | eMMC | UFS | LPDDR | LPDDR2 | LPDDR3 | LPDDR4 | LPDDR4X | LPDDR5 |
             DDR | DDR2 | DDR3 | DDR4 | DDR5 | SDRAM | NOR Flash | SRAM | SoC | CPU | Baseband
"""

GEMINI_EMCP_FOLLOWUP = """O chip com Part Number {pn} foi identificado como {chip_type} da marca {brand}.

Preciso ESPECIFICAMENTE das capacidades:
1. Quanto de RAM? (tipo LPDDR + GB)
2. Quanto de NAND? (versão eMMC + GB)

Busque em: preduo.com, censtry.com, serviceemmc.com, wolfchip.com, glochip.com, jotrin.com

Responda APENAS com JSON válido:
{{
  "ram": "tipo e capacidade da RAM",
  "nand": "versão eMMC e capacidade",
  "device": "dispositivo que usa este chip (se souber)",
  "source_url": "URL de onde veio a informação (se houver)",
  "confidence": "high|medium|low",
  "reasoning": "de onde vieram os dados"
}}
"""

GEMINI_MODELS_FALLBACK = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]


def _get_api_key() -> str:
    from django.conf import settings
    # Respeita o flag GEMINI_ENABLED — se False, retorna string vazia, o que faz
    # _gemini_lookup() e _gemini_emcp_followup() retornarem None imediatamente.
    if not getattr(settings, "GEMINI_ENABLED", False):
        return ""
    return getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")


def _extract_json_from_text(raw: str) -> dict | None:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    break
    return None


def _gemini_api_call(url: str, prompt: str, use_grounding: bool, timeout: int = 20) -> str | None:
    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
    }
    if use_grounding:
        payload["tools"] = [{"google_search": {}}]
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        parts = []
        for cand in data.get("candidates", []):
            for p in cand.get("content", {}).get("parts", []):
                if "text" in p:
                    parts.append(p["text"])
        return "".join(parts).strip() or None
    except urllib.error.HTTPError as e:
        if e.code in (400, 403):
            raise
        return None
    except Exception:
        return None


def _gemini_lookup(pn: str, family_hint: str = "") -> dict | None:
    """Consulta Gemini com Google Search grounding. Fallback sem grounding se necessário."""
    api_key = _get_api_key()
    if not api_key:
        return None

    hint_text = f"Contexto já identificado: {family_hint}\n" if family_hint else ""
    prompt = GEMINI_PROMPT.format(pn=pn, family_hint=hint_text)

    for model in GEMINI_MODELS_FALLBACK:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        # Tentativa 1: com grounding
        try:
            raw = _gemini_api_call(url, prompt, use_grounding=True)
            if raw:
                result = _extract_json_from_text(raw)
                if result and result.get("chip_type"):
                    result["_grounded"] = True
                    return result
        except urllib.error.HTTPError as e:
            if e.code not in (400, 403):
                continue

        # Tentativa 2: sem grounding
        try:
            raw = _gemini_api_call(url, prompt, use_grounding=False)
            if raw:
                result = _extract_json_from_text(raw)
                if result and result.get("chip_type"):
                    result["_grounded"] = False
                    return result
        except Exception:
            pass

    return None


def _gemini_emcp_followup(pn: str, chip_type: str, brand: str) -> dict | None:
    """Segundo chamado cirúrgico para eMCP sem capacidade RAM/NAND."""
    api_key = _get_api_key()
    if not api_key:
        return None

    prompt = GEMINI_EMCP_FOLLOWUP.format(pn=pn, chip_type=chip_type, brand=brand or "desconhecida")

    for model in GEMINI_MODELS_FALLBACK:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        for use_grounding in (True, False):
            try:
                raw = _gemini_api_call(url, prompt, use_grounding=use_grounding, timeout=20)
                if raw:
                    result = _extract_json_from_text(raw)
                    if result and (
                        _CAP_RE.search(str(result.get("ram") or "")) or
                        _CAP_RE.search(str(result.get("nand") or ""))
                    ):
                        return result
            except urllib.error.HTTPError as e:
                if e.code in (400, 403):
                    break
            except Exception:
                pass

    return None


def _specs_are_complete(specs: dict) -> bool:
    """Gate de qualidade antes de persistir no banco."""
    chip_type = (specs.get("chip_type") or "").lower().replace(" ", "")
    if not chip_type:
        return False
    if chip_type in ("soc", "cpu", "baseband"):
        return bool(specs.get("brand"))
    if chip_type in ("emcp", "umcp"):
        return bool(
            _CAP_RE.search(str(specs.get("ram") or "")) and
            _CAP_RE.search(str(specs.get("nand") or ""))
        )
    if chip_type in ("norflash", "sram"):
        return bool(
            _CAP_RE.search(str(specs.get("capacity") or "")) or
            specs.get("interface")
        )
    return bool(_CAP_RE.search(str(specs.get("capacity") or "")))


def _save_gemini_to_db(pn: str, specs: dict):
    """Salva resultado do Gemini no banco com status='enriched'."""
    try:
        brand_name = specs.get("brand", "Desconhecido")
        conf_raw   = specs.get("confidence", "low")
        conf_map   = {"high": "ai_high", "medium": "ai_medium", "low": "ai_low"}
        confidence = conf_map.get(conf_raw, "ai_low")

        # get_or_create não aceita lookups (name__iexact) como campo de criação.
        # Usamos filter().first() + create() para evitar FieldError em marcas novas.
        brand = Brand.objects.filter(name__iexact=brand_name).first()
        if not brand:
            brand = Brand.objects.create(
                name=brand_name,
                code=brand_name.upper()[:10].replace(" ", ""),
            )
        # Uma única Source compartilhada para todos os resultados Gemini.
        # Antes criava um registro por PN (url=f"gemini:{pn}"), gerando
        # milhares de entradas "Gemini Live Search" idênticas no banco.
        source, _ = Source.objects.get_or_create(
            url="gemini:live-search",
            defaults={"name": "Gemini Live Search", "src_type": "ai"}
        )
        family = _match_family(pn)

        part, created = KnownPart.objects.get_or_create(
            part_number=pn,
            defaults={
                "brand":      brand,
                "family":     family,
                "status":     "enriched",
                "chip_type":  specs.get("chip_type") or "",
                "emcp_ram":   specs.get("ram")       or "",
                "emcp_nand":  specs.get("nand")      or "",
                "capacity":   specs.get("capacity")  or "",
                "interface":  specs.get("interface") or "",
                "device":     specs.get("device")    or "",
                "notes":      str(specs.get("reasoning") or ""),
                "confidence": confidence,
                "source":     source,
                "source_url": f"gemini:{pn}",
            }
        )
        if not created:
            changed = False
            updates = {
                "chip_type": specs.get("chip_type"),
                "capacity":  specs.get("capacity"),
                "interface": specs.get("interface"),
                "device":    specs.get("device"),
                "emcp_ram":  specs.get("ram"),
                "emcp_nand": specs.get("nand"),
            }
            for field, val in updates.items():
                if val and not getattr(part, field):
                    setattr(part, field, val)
                    changed = True
            if part.status == "raw":
                part.status = "enriched"
                changed = True
            if changed:
                part.save()
        return part
    except Exception:
        logger.exception("Erro ao salvar resultado do Gemini no banco para PN=%s", pn)
        return None


def _persist_grammar_result(pn: str, fam, result: dict):
    """
    Persiste resultado completo da gramática no banco como KnownPart enriched.

    Chamado apenas quando grammar_complete=True e pn_short=False.

    Regra de confiança — não sobrescreve se a entrada existente tiver
    confiança melhor que 'estimated':
        confirmed > manual > distributor > ai_high > ai_medium > ai_low > estimated

    Retorna o KnownPart salvo, ou None em caso de erro.
    """
    _CONF_PRIORITY = {
        "confirmed": 7, "manual": 6, "distributor": 5,
        "ai_high": 4, "ai_medium": 3, "ai_low": 2, "estimated": 1,
    }
    try:
        from django.db import transaction

        new_fields = {
            "chip_type":  result.get("chip_type")  or "",
            "subtype":    result.get("subtype")     or "",
            "interface":  result.get("interface")   or "",
            "emcp_ram":   result.get("emcp_ram")    or "",
            "emcp_nand":  result.get("emcp_nand")   or "",
            "capacity":   result.get("capacity")    or "",
        }

        part, created = KnownPart.objects.get_or_create(
            part_number=pn,
            defaults={
                "brand":      fam.brand,
                "family":     fam,
                "status":     "enriched",
                "confidence": "estimated",
                "notes":      f"Auto-persistido pela gramática. Família: {fam.prefix}",
                **new_fields,
            },
        )

        if not created:
            # Nunca sobrescreve entradas com confiança acima de 'estimated'
            existing_priority = _CONF_PRIORITY.get(part.confidence, 0)
            if existing_priority > _CONF_PRIORITY["estimated"]:
                logger.debug(
                    "_persist_grammar_result: PN=%s já tem confidence=%s — skip",
                    pn, part.confidence,
                )
                return part

            # Atualiza campos ainda vazios; promove status raw → enriched
            changed = False
            for field, val in new_fields.items():
                if val and not getattr(part, field, ""):
                    setattr(part, field, val)
                    changed = True
            if part.status == "raw":
                part.status = "enriched"
                changed = True
            if changed:
                with transaction.atomic():
                    part.save()

        return part

    except Exception:
        logger.exception("Erro ao persistir resultado da gramática PN=%s", pn)
        return None


def _build_result_from_gemini(pn: str, specs: dict, part) -> dict:
    chip_type = specs.get("chip_type", "")
    is_emcp   = chip_type in ("eMCP", "uMCP")
    family    = _match_family(pn)
    conf_map  = {"high": "ai_high", "medium": "ai_medium", "low": "ai_low"}

    return {
        "pn":            pn,
        "known":         True,
        "known_exact":   part is not None,
        "chip_type":     chip_type,
        "subtype":       specs.get("subtype", ""),
        "interface":     specs.get("interface", ""),
        "family_prefix": family.prefix if family else "",
        "brand":         specs.get("brand", ""),
        "is_emcp":       is_emcp,
        "tip":           specs.get("reasoning", ""),
        "reasoning":     [],
        "doc_url":       _doc_url(family),
        "capacity":      specs.get("capacity"),
        "dram_density":  None,
        "emcp_ram":      specs.get("ram"),
        "emcp_nand":     specs.get("nand"),
        "emcp_device":   specs.get("device") if is_emcp else None,
        "emcp_source":   conf_map.get(specs.get("confidence", "low"), "ai_low"),
        "device":        specs.get("device") if not is_emcp else None,
        "confidence":    conf_map.get(specs.get("confidence", "low"), "ai_low"),
        "source_url":    specs.get("source_url"),
        "from_web":      True,
        "gemini_found":  True,
        "suffix_note":   None,
        "remarked_flag": False,
        "fuzzy_suggestions": [],
        "classification_source": "Gemini",
    }


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


# ── Ponto de entrada público ───────────────────────────────────────────────────

def classify(pn_raw: str) -> dict:
    """
    Classifica um Part Number.

    Fluxo:
      1. Banco exato (enriched) → resultado completo
      2. Gramática da família   → decodificação + Gemini se campos essenciais vazios
      3. Gemini puro            → PN desconhecido
      4. Fuzzy matching         → sugestões de digitação
    """
    pn = pn_raw.upper().strip()
    pn = re.sub(r"[^A-Z0-9]", "", pn)

    if not pn:
        return {"pn": pn_raw, "known": False, "error": "PN inválido"}

    # ── Detecta PN potencialmente truncado ──────────────────────────────────
    # Se a família tem pn_length definido e o PN digitado é mais curto, tratamos
    # como "possivelmente truncado" e pulamos o lookup no DB por segurança.
    # Isso evita que registros acidentais (ex: "KMDC" alucinado pelo Gemini com
    # 64GB+4GB) sejam retornados enquanto o operador ainda está digitando.
    # Nota: pn_short != pn_incomplete. Um PN pode ser curto mas a gramática já
    # retornar resultado completo (ex: KLMCGUCTA/9 chars: capacidade em pn[3]).
    # O aviso visual só aparece quando o resultado da gramática também for parcial.
    fam_early = _match_family(pn)
    pn_short = bool(
        fam_early and fam_early.pn_length and len(pn) < fam_early.pn_length
    )

    # ── 1. Busca exata no banco ──────────────────────────────────────────────
    # Pulado quando PN está visivelmente curto — evita acerto acidental em
    # registros criados para PNs truncados (OCR parcial, digitação incompleta).
    if not pn_short:
        try:
            known = KnownPart.objects.select_related("family", "brand", "family__doc_page").get(
                part_number=pn, status="enriched"
            )
            # Preferir ChipFamily pelo prefixo — mais confiável que o chip_type
            # salvo pelo Gemini (que pode ter classificado errado, ex: uMCP como eMCP).
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
                    "remarked_flag": False,
                    "fuzzy_suggestions": [],
                    "interface":    known.interface,
                    "family_prefix": "",
                }
            _log_search(pn, found=True, source_used="db_exact")
            return result
        except KnownPart.DoesNotExist:
            pass

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

        # Decide se precisa do Gemini para completar
        # PN com resultado incompleto e ainda curto nunca vai ao Gemini —
        # não faz sentido enriquecer algo que o operador ainda está digitando.
        missing_emcp = (not pn_incomplete) and not grammar_complete and fam.is_emcp
        missing_cap  = (not pn_incomplete) and not grammar_complete and not fam.is_emcp

        _gemini_saved_now = False  # inicializa antes do bloco condicional

        if missing_emcp or missing_cap:
            hint = f"{fam.chip_type} {fam.subtype or ''} da família '{fam.prefix}'"
            specs = _gemini_lookup(pn, family_hint=hint)

            if specs is not None:
                if not specs.get("chip_type"):
                    specs["chip_type"] = fam.chip_type

                # Segundo chamado cirúrgico para eMCP sem capacidade
                chip_t = (specs.get("chip_type") or "").lower()
                if chip_t in ("emcp", "umcp"):
                    has_ram  = _CAP_RE.search(str(specs.get("ram") or ""))
                    has_nand = _CAP_RE.search(str(specs.get("nand") or ""))
                    if not has_ram or not has_nand:
                        followup = _gemini_emcp_followup(
                            pn, specs.get("chip_type", "eMCP"), specs.get("brand", "")
                        )
                        if followup:
                            for key in ("ram", "nand", "device", "source_url"):
                                if followup.get(key) and not specs.get(key):
                                    specs[key] = followup[key]

                # Salva no banco sempre que temos ao menos chip_type.
                # Antes era limitado a _specs_are_complete, mas isso causava
                # re-consulta ao Gemini em toda busca quando a resposta era parcial.
                # Agora salvamos sempre — resultado incompleto é melhor que zero cache.
                if specs.get("chip_type"):
                    _gemini_saved_now = _save_gemini_to_db(pn, specs) is not None

                # Mescla dados Gemini
                if specs.get("capacity"):
                    grammar_result["capacity"] = specs["capacity"]
                if grammar_result.get("is_emcp"):
                    if specs.get("ram"):
                        grammar_result["emcp_ram"]  = specs["ram"]
                    if specs.get("nand"):
                        grammar_result["emcp_nand"] = specs["nand"]
                    if specs.get("device"):
                        grammar_result["emcp_device"] = specs["device"]
                    grammar_result["emcp_source"] = "gemini"
                else:
                    if specs.get("device"):
                        grammar_result["device"] = specs["device"]
                    if specs.get("interface") and not grammar_result.get("interface"):
                        grammar_result["interface"] = specs["interface"]

                grammar_result["gemini_found"]  = True
                grammar_result["known_exact"]   = True
                grammar_result["classification_source"] = "Gramática + Gemini"
            else:
                grammar_result["gemini_searched"] = True
                grammar_result["gemini_found"]    = False

        # Double-check: compara gramática com banco se PN já existia como enriched
        # ANTES desta execução. Se o Gemini acabou de criar o registro agora
        # (_gemini_saved_now=True), não comparamos — os dados são os mesmos.
        if not _gemini_saved_now:
            try:
                db_part = KnownPart.objects.get(part_number=pn, status="enriched")
                if db_part.family:
                    db_result = _result_from_known(pn, db_part, db_part.family)
                    if _check_remarked(grammar_result, db_result):
                        grammar_result["remarked_flag"] = True
                        # BUG-1: antes usava capacity/dram_density, que são None para
                        # eMCP/uMCP → exibia "gramática indica None, banco confirma None".
                        # _remarked_summary() cobre emcp_nand/emcp_ram também.
                        grammar_result["remarked_note"] = (
                            f"⚠️ Atenção: gramática indica "
                            f"{_remarked_summary(grammar_result)}, "
                            f"banco confirma "
                            f"{_remarked_summary(db_result)}. "
                            f"Verificar possível chip remarked."
                        )
            except KnownPart.DoesNotExist:
                pass

        # ── Fila de revisão ───────────────────────────────────────────────────
        # Chips com gramática completa (NAND+RAM ou capacidade decodificados)
        # NÃO vão para revisão — o resultado já é confiável.
        # Só chips com gramática parcial/incompleta precisam de enriquecimento manual.
        _in_review_queue = False
        if not _gemini_saved_now and not grammar_complete:
            try:
                if not KnownPart.objects.filter(part_number=pn, status="enriched").exists():
                    KnownPart.objects.get_or_create(
                        part_number=pn,
                        defaults={
                            "status":    "raw",
                            "brand":     fam.brand,
                            "family":    fam,
                            "chip_type": fam.chip_type or "",
                            "notes": (
                                f"Fila de revisão: família={fam.prefix}, "
                                f"grammar_complete={grammar_complete}"
                            ),
                        },
                    )
                    _in_review_queue = True
            except Exception:
                logger.exception("Erro ao enfileirar PN=%s na fila de revisão", pn)

        grammar_result["grammar_complete"]  = grammar_complete
        grammar_result["in_review_queue"]   = _in_review_queue
        grammar_result["grammar_persisted"] = False  # mantido para compatibilidade

        _log_search(pn, found=True, source_used="grammar")
        return grammar_result

    # ── 3. Gemini puro (prefixo desconhecido) ────────────────────────────────
    _log_unknown(pn)
    specs = _gemini_lookup(pn)

    if specs and specs.get("chip_type"):
        chip_t = (specs.get("chip_type") or "").lower()
        if chip_t in ("emcp", "umcp"):
            has_ram  = _CAP_RE.search(str(specs.get("ram") or ""))
            has_nand = _CAP_RE.search(str(specs.get("nand") or ""))
            if not has_ram or not has_nand:
                followup = _gemini_emcp_followup(
                    pn, specs.get("chip_type", "eMCP"), specs.get("brand", "")
                )
                if followup:
                    for key in ("ram", "nand", "device", "source_url"):
                        if followup.get(key) and not specs.get(key):
                            specs[key] = followup[key]

        part = _save_gemini_to_db(pn, specs) if specs.get("chip_type") else None
        result = _build_result_from_gemini(pn, specs, part)
        _log_search(pn, found=True, source_used="gemini")
        return result

    # ── 4. Fuzzy matching como sugestão ──────────────────────────────────────
    # _log_unknown() já gravou em UnknownChip — família completamente desconhecida.
    suggestions = _fuzzy_candidates(pn)
    _log_search(pn, found=False, source_used="not_found")

    return {
        "pn":               pn,
        "known":            False,
        "from_web":         True,
        "gemini_found":     False,
        "gemini_searched":  True,
        "fuzzy_suggestions": [s.part_number for s in suggestions],
        "in_review_queue":  True,   # UnknownChip já logado por _log_unknown()
    }
