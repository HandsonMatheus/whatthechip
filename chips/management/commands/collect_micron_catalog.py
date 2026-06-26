"""
collect_micron_catalog.py — Varredura massiva do catálogo Micron (famílias completas)
=====================================================================================
Coleta TODAS as famílias Micron de chips mais comuns na reciclagem de smartphones
(eMMC, eMCP, uMCP, LPDDR2/3/4/4X/5) usando a API FBGA oficial da Micron.

Ao contrário de collect_preduo_bulk (que coleta PN por PN de um marketplace),
este script faz uma varredura sistemática em FAMÍLIAS INTEIRAS de chips, escalando
para centenas de PNs sem intervenção manual.

═══════════════════════════════════════════════════════════════════
ESTRATÉGIAS (executadas em sequência, da mais eficiente para a mais granular)
═══════════════════════════════════════════════════════════════════

1. SUBCATEGORIA — Consulta a API Micron por sub-categoria (uma request = família toda)
   Endpoint: /getpartbyfbgacode/-/-/-/en_US/{subcategoria}/-/-
   Ex: "obsolete-emmc-based-mcp" → retorna todos os eMCPs obsoletos de uma vez

2. SEMENTE FBGA — Expande famílias a partir de FBGAs conhecidos (da bancada + banco)
   FBGA → lookup reverso → PN base → lookup direto → TODOS os FBGAs da família
   Ex: JW464 → MT29PZZZ4C2BKFTF → JW464, JW465, JW466... (família inteira)

3. PREFIXO PN — Varre prefixos de Part Number conhecidos (gerações completas)
   Ex: MT29PZZZ, MT29VZZZ, MTFC4G, MTFC8G... → variantes por capacidade/spec

4. WAYBACK CDX — Extrai PNs do índice do Wayback Machine (arquivo histórico)
   CDX API: web.archive.org/cdx para URLs de datasheets Micron 2012-2020

Todos os resultados são salvos diretamente com confidence='confirmed'
(fonte: API oficial Micron), sem necessidade de passar pelo enrich_micron_fbga.

═══════════════════════════════════════════════════════════════════
USO
═══════════════════════════════════════════════════════════════════
    python manage.py collect_micron_catalog
    python manage.py collect_micron_catalog --dry-run
    python manage.py collect_micron_catalog --strategy all        # todas as estratégias
    python manage.py collect_micron_catalog --strategy subcat     # só subcategorias
    python manage.py collect_micron_catalog --strategy seed       # só expansão de sementes
    python manage.py collect_micron_catalog --strategy prefix     # só prefixos de PN
    python manage.py collect_micron_catalog --strategy wayback    # só Wayback CDX
    python manage.py collect_micron_catalog --delay 2.0
    python manage.py collect_micron_catalog --limit 200
    python manage.py collect_micron_catalog --no-wayback          # pula Wayback (mais rápido)
    python manage.py collect_micron_catalog --verbose             # debug HTTP
"""

import re
import time
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

# ── API Micron FBGA ───────────────────────────────────────────────────────────
#
# Mesma API usada pelo enrich_micron_fbga.py e lookup_fbga.py.
# Os 7 segmentos após getpartbyfbgacode são:
#   {product-line} / {product-family} / {part-type} / {locale} / {sub-category} / {pn} / {fbga}
# Usar "-" como wildcard em qualquer campo.
#
_FBGA_API_BASE = (
    "https://www.micron.com/content/micron/us/en/sales-support/design-tools/"
    "fbga-parts-decoder/_jcr_content.products.json/getpartbyfbgacode"
)

# Busca por PN (retorna todos os FBGAs de um PN base)
MICRON_API_BY_PN   = _FBGA_API_BASE + "/-/-/-/en_US/-/{pn}/-"
# Busca reversa por FBGA (retorna o PN correspondente)
MICRON_API_BY_FBGA = _FBGA_API_BASE + "/-/-/-/en_US/-/-/{fbga}"
# Busca por sub-categoria (retorna TODOS os chips dessa sub-categoria)
MICRON_API_BY_SUBCAT = _FBGA_API_BASE + "/-/-/-/en_US/{subcat}/-/-"

MICRON_FBGA_SOURCE_URL = (
    "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": MICRON_FBGA_SOURCE_URL,
}

_FBGA_RE = re.compile(r"^[A-Z0-9]{5}$")

# ── Sementes: FBGAs conhecidos da bancada de reciclagem ───────────────────────
#
# Estes são chips reais identificados na bancada pelo usuário.
# Servem como pontos de entrada para descobrir as famílias completas.
# Adicione mais à medida que novos chips forem identificados.
#
FBGA_SEEDS = [
    # eMMC/eMCP — prefixo J (famílias antigas, 2013-2018)
    "JW464",  # eMCP  ~16GB+2GB  (família JW — muito comum na reciclagem)
    "JWB13",  # eMCP  ~32GB      (família JWB)
    "JZ185",  # eMCP             (família JZ)
    "JY934",  # eMCP             (família JY)
    "JY941",  # eMCP             (família JY)
    "JWA60",  # eMCP             (família JWA)
    "JZ177",  # eMCP             (família JZ — único reconhecido na bancada)
    "JZ109",  # eMCP             (família JZ)
    # LPDDR — prefixo D9 (Micron DRAM, também comum)
    "D9RRD",  # LPDDR            (família D9)
    # Adicione novos seeds aqui conforme necessário
]

# ── Sub-categorias Micron para varredura direta ───────────────────────────────
#
# Nomes inferidos do campo "sub-category" nas respostas da API.
# A API pode suportar estes como parâmetro de path; se não suportar,
# a request retornará vazio e a estratégia será pulada graciosamente.
#
MICRON_SUBCATEGORIES = [
    # eMCP / uMCP (os mais importantes para reciclagem de smartphones)
    "obsolete-emmc-based-mcp",       # eMCP obsoleto (JW, JY, JZ — bancada)
    "emmc-based-mcp",                # eMCP atual
    "lpddr4-emmc-based-mcp",         # eMCP + LPDDR4
    "lpddr3-emmc-based-mcp",         # eMCP + LPDDR3
    "lpddr2-emmc-based-mcp",         # eMCP + LPDDR2 (mais antigos)
    "umcp",                          # uMCP (Universal MCP — mais novos)
    # eMMC standalone
    "emmc",                          # eMMC standalone
    "obsolete-emmc",                 # eMMC obsoleto
    # LPDDR standalone (chips D9)
    "lpddr5",
    "lpddr4x",
    "lpddr4",
    "lpddr3",
    "lpddr2",                        # LPDDR2 — os mais antigos
]

# ── Prefixos de PN para varredura sistemática ────────────────────────────────
#
# Cada entrada é (prefixo_base, chip_type, subtype, descrição).
# A varredura tenta o prefixo + variações de capacidade/spec.
#
PN_PREFIXES = [
    # ─── eMCP (eMMC + LPDDR embutido) ─────────────────────────────────────
    # MT29P = eMCP com LPDDR2 (2011-2016, muito comum em Samsung/LG antigos)
    ("MT29PZZZ",   "eMCP", "LPDDR2", "eMCP com LPDDR2 (geração antiga)"),
    # MT29V = eMCP com LPDDR3/4 (2014-2018)
    ("MT29VZZZ",   "eMCP", "LPDDR3", "eMCP com LPDDR3 (2014-2018)"),
    # MT29T = eMCP com LPDDR3 (variante)
    ("MT29TZZZ",   "eMCP", "LPDDR3", "eMCP com LPDDR3 (variante T)"),
    # MT30A = uMCP com LPDDR5 (mais novo)
    ("MT30AZZZ",   "uMCP", "LPDDR5", "uMCP com LPDDR5 (2019+)"),
    # ─── eMMC standalone ──────────────────────────────────────────────────
    # MTFC = eMMC standalone (maioria dos chips de tablets/TVs)
    ("MTFC4G",     "eMMC", "",       "eMMC 4GB standalone"),
    ("MTFC8G",     "eMMC", "",       "eMMC 8GB standalone"),
    ("MTFC16G",    "eMMC", "",       "eMMC 16GB standalone"),
    ("MTFC32G",    "eMMC", "",       "eMMC 32GB standalone"),
    ("MTFC64G",    "eMMC", "",       "eMMC 64GB standalone"),
    ("MTFC128G",   "eMMC", "",       "eMMC 128GB standalone"),
    ("MTFD",       "eMMC", "",       "eMMC MTFD series"),
    # ─── LPDDR standalone ─────────────────────────────────────────────────
    ("MT52",       "LPDDR", "LPDDR3", "LPDDR3 DRAM (MT52 series)"),
    ("MT53",       "LPDDR", "LPDDR4", "LPDDR4/4X DRAM (MT53 series)"),
    ("MT62",       "LPDDR", "LPDDR4X","LPDDR4X DRAM (MT62 series)"),
    ("MT63",       "LPDDR", "LPDDR4X","LPDDR4X high-density (MT63 series)"),
    ("MT64",       "LPDDR", "LPDDR5", "LPDDR5 DRAM (MT64 series)"),
]

# ── Wayback CDX — padrões de URL para buscar PNs em arquivos históricos ───────
#
# Formato CDX: http://web.archive.org/cdx/search/cdx?url={pattern}&output=json...
# Extraímos PNs dos caminhos de URL (datasheets nomeados pelo PN).
#
WAYBACK_CDX_PATTERNS = [
    # Datasheets de eMCP/eMCP antigos (2012-2019)
    "micron.com/~/media/documents/products/data-sheet/flash/e-mcp/*",
    "micron.com/~/media/documents/products/data-sheet/flash/emmc/*",
    "micron.com/~/media/documents/products/data-sheet/lpdram/*",
    "micron.com/~/media/documents/products/data-sheet/dram/lpddr*",
    # Páginas de produto (URLs com PN no caminho)
    "micron.com/products/managed-nand/e-mcp/*",
    "micron.com/products/managed-nand/emmc/*",
    "micron.com/products/dram/lpddr*",
]

# Regex para extrair PN Micron de URLs/textos
_MICRON_PN_RE = re.compile(
    r"\b(MT(?:29[PVTF]|30A|52|53|62|63|64|FC|FD)[A-Z0-9]{4,}|"
    r"MTFC\d+G[A-Z0-9-]+)\b",
    re.IGNORECASE,
)

# Prefixos de PN para validação como chip mobile Micron
MOBILE_PREFIXES = (
    "MT29V", "MT29T", "MT29P", "MT30A",
    "MTFC", "MTFD",
    "MT29F4G", "MT29F8G",  # NAND flash antigo
    "MT52", "MT53", "MT62", "MT63", "MT64",
)


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
    """curl_cffi preferido (TLS Chrome) para contornar proteções Cloudflare."""
    try:
        from curl_cffi import requests as cffi_requests
        s = cffi_requests.Session(impersonate="chrome110")
        s._is_cffi = True
        return s
    except ImportError:
        import requests as std_requests
        s = std_requests.Session()
        s._is_cffi = False
        return s


# ── Consulta API Micron ───────────────────────────────────────────────────────

def _api_get(url: str, session, retries: int = 3, verbose: bool = False) -> dict | list | None:
    """GET genérico com retry e back-off. Retorna JSON parsed ou None."""
    for attempt in range(retries):
        try:
            if verbose:
                print(f"  [HTTP GET] {url}")
            r = session.get(url, headers=_HEADERS, timeout=30)
            if verbose:
                print(f"  [HTTP {r.status_code}] {len(r.content)} bytes")

            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    if verbose:
                        print(f"  [WARN] Resposta não-JSON: {r.text[:200]!r}")
                    return None

            elif r.status_code == 404:
                return None  # não encontrado — normal

            elif r.status_code in (429, 503):
                wait = 8 * (attempt + 1)
                logger.warning("HTTP %s (rate-limit) — aguardando %ds", r.status_code, wait)
                time.sleep(wait)
                continue

            else:
                logger.debug("HTTP %s para %s (tentativa %d)", r.status_code, url, attempt + 1)

        except Exception as e:
            logger.warning("Erro tentativa %d/%d: %s", attempt + 1, retries, e)

        time.sleep(2 * (attempt + 1))

    return None


def _parse_api_response(data) -> list[dict]:
    """
    Parseia resposta da API FBGA Micron.
    Retorna lista de {"fbga_code", "part_number", "sub_category", "source_url"}.
    """
    if data is None:
        return []

    # Normaliza para lista de itens
    if isinstance(data, dict):
        items = (
            data.get("details")
            or data.get("results")
            or data.get("data")
            or data.get("products")
            or data.get("items")
            or []
        )
    elif isinstance(data, list):
        items = data
    else:
        return []

    results = []
    seen_fbgas: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        fbga = (
            item.get("fbga-code")
            or item.get("fbgaCode")
            or item.get("fbga_code")
            or item.get("fbga")
            or ""
        ).strip().upper()

        full_pn = (
            item.get("part-number")
            or item.get("partNumber")
            or item.get("part_number")
            or item.get("pn")
            or ""
        ).strip()

        sub_cat = (
            item.get("sub-category")
            or item.get("subCategory")
            or item.get("sub_category")
            or ""
        ).strip().lower()

        page_url = item.get("pageurl", "").strip()
        if page_url and not page_url.startswith("http"):
            page_url = f"https://www.micron.com{page_url}"

        if not fbga or not full_pn:
            continue
        if not _FBGA_RE.match(fbga):
            logger.debug("FBGA inválido ignorado: %r", fbga)
            continue
        if fbga in seen_fbgas:
            continue

        seen_fbgas.add(fbga)
        results.append({
            "fbga_code":    fbga,
            "part_number":  full_pn,
            "sub_category": sub_cat,
            "source_url":   page_url or MICRON_FBGA_SOURCE_URL,
        })

    return results


# ── Estratégia 1: Sub-categoria ───────────────────────────────────────────────

def _sweep_subcategories(
    session,
    subcategories: list[str],
    delay: float,
    verbose: bool,
    log_fn,
) -> list[dict]:
    """
    Consulta a API por sub-categoria.
    Cada sub-categoria bem-sucedida retorna TODA a família de chips.
    """
    all_results: list[dict] = []
    found_subcats: list[str] = []

    log_fn("\n═══ Estratégia 1: Varredura por sub-categoria ═══")

    for subcat in subcategories:
        url = MICRON_API_BY_SUBCAT.format(subcat=subcat)
        data = _api_get(url, session, verbose=verbose)
        parsed = _parse_api_response(data)

        if parsed:
            log_fn(
                f"  ✓  sub-categoria '{subcat}': {len(parsed)} chips encontrados"
            )
            for item in parsed:
                item["strategy"] = f"subcat:{subcat}"
            all_results.extend(parsed)
            found_subcats.append(subcat)
        else:
            log_fn(f"  –  sub-categoria '{subcat}': sem resultados")

        time.sleep(delay)

    if not found_subcats:
        log_fn(
            "  ℹ  API não suporta busca por sub-categoria (retornou vazio para todas).\n"
            "     Isso é esperado — continuando com as próximas estratégias."
        )
    else:
        log_fn(
            f"\n  Sub-categorias com resultado: {', '.join(found_subcats)}\n"
            f"  Total chips descobertos: {len(all_results)}"
        )

    return all_results


# ── Estratégia 2: Expansão de sementes FBGA ──────────────────────────────────

def _expand_fbga_seeds(
    session,
    seeds: list[str],
    delay: float,
    verbose: bool,
    log_fn,
) -> list[dict]:
    """
    Para cada FBGA semente:
      1. Lookup reverso: FBGA → PN completo
      2. Extrai PN base (remove sufixos de packaging/temp/speed)
      3. Lookup direto: PN base → TODOS os FBGAs da família

    Isso permite que 1 FBGA da bancada expanda para dezenas de irmãos.
    """
    all_results: list[dict] = []
    discovered_pn_bases: set[str] = set()

    log_fn("\n═══ Estratégia 2: Expansão de sementes FBGA ═══")
    log_fn(f"  Sementes: {', '.join(seeds)}")

    # Fase 2a: FBGA → PN base
    log_fn("\n  Fase 2a: Lookup reverso (FBGA → PN)...")

    fbga_to_pn: dict[str, str] = {}

    for fbga in seeds:
        url = MICRON_API_BY_FBGA.format(fbga=fbga)
        data = _api_get(url, session, verbose=verbose)
        parsed = _parse_api_response(data)

        if parsed:
            # Pega o primeiro PN retornado
            full_pn = parsed[0]["part_number"]
            base_pn = _extract_pn_base(full_pn)
            fbga_to_pn[fbga] = base_pn
            log_fn(f"  ✓  {fbga} → {full_pn} (base: {base_pn})")
        else:
            log_fn(f"  ✗  {fbga}: não encontrado na API Micron")

        time.sleep(delay)

    # Fase 2b: PN base → família completa
    log_fn("\n  Fase 2b: Lookup direto (PN base → família completa)...")

    # Agrupa FBGAs que levaram ao mesmo PN base (evita duplicar requests)
    pn_to_seeds: dict[str, list[str]] = {}
    for fbga, pn_base in fbga_to_pn.items():
        pn_to_seeds.setdefault(pn_base, []).append(fbga)

    for pn_base, seed_fbgas in pn_to_seeds.items():
        if pn_base in discovered_pn_bases:
            continue
        discovered_pn_bases.add(pn_base)

        url = MICRON_API_BY_PN.format(pn=pn_base)
        data = _api_get(url, session, verbose=verbose)
        parsed = _parse_api_response(data)

        if parsed:
            log_fn(
                f"  ✓  {pn_base} (via semente {seed_fbgas[0]}): "
                f"{len(parsed)} FBGAs na família"
            )
            for item in parsed:
                item["strategy"] = f"seed:{seed_fbgas[0]}"
            all_results.extend(parsed)
        else:
            log_fn(f"  ✗  {pn_base}: nenhuma família encontrada")

        time.sleep(delay)

    log_fn(f"\n  FBGAs descobertos via sementes: {len(all_results)}")
    return all_results


def _extract_pn_base(full_pn: str) -> str:
    """
    Extrai o PN base de um PN completo Micron.

    Micron PNs têm formato: {BASE}-{packaging} {temp/speed}.
    Ex: "MT29PZZZ8D5BKFTF-18 W.95L" → "MT29PZZZ8D5BKFTF"
        "MT29VZZZZAD8GQFSL-046 W.9R8" → "MT29VZZZZAD8GQFSL"

    Remove tudo após '-' ou ' ' que são sufixos de packaging.
    """
    # Remove sufixo após '-' (packaging grade)
    pn = full_pn.split("-")[0].strip()
    # Remove sufixo após ' ' (speed/temp bin)
    pn = pn.split(" ")[0].strip()
    return pn.upper()


# ── Estratégia 3: Varredura por prefixo de PN ─────────────────────────────────

def _sweep_pn_prefixes(
    session,
    prefixes: list[tuple],
    delay: float,
    verbose: bool,
    log_fn,
) -> list[dict]:
    """
    Para cada prefixo de PN (ex: MT29PZZZ), consulta a API Micron.
    A API pode suportar correspondência por prefixo parcial.
    Se não suportar, tenta variações sistemáticas de capacidade.
    """
    all_results: list[dict] = []
    queried_prefixes: set[str] = set()

    log_fn("\n═══ Estratégia 3: Varredura por prefixo de PN ═══")

    for pn_prefix, chip_type, subtype, description in prefixes:
        if pn_prefix in queried_prefixes:
            continue
        queried_prefixes.add(pn_prefix)

        log_fn(f"\n  Prefixo: {pn_prefix} ({description})")

        # Tentativa 1: prefixo direto (API pode suportar)
        url = MICRON_API_BY_PN.format(pn=pn_prefix)
        data = _api_get(url, session, verbose=verbose)
        parsed = _parse_api_response(data)

        if parsed:
            log_fn(f"  ✓  {pn_prefix}: {len(parsed)} chips (prefixo direto)")
            for item in parsed:
                item["strategy"]  = f"prefix:{pn_prefix}"
                item["chip_type"] = item.get("chip_type") or chip_type
                item["subtype"]   = item.get("subtype") or subtype
            all_results.extend(parsed)
        else:
            # Tentativa 2: variações de capacidade (caso a API exija PN mais completo)
            log_fn(f"  –  prefixo direto sem resultado — tentando variações...")
            variants = _generate_pn_variants(pn_prefix)
            found_any = False
            for variant in variants:
                if variant == pn_prefix:
                    continue
                url_v = MICRON_API_BY_PN.format(pn=variant)
                data_v = _api_get(url_v, session, verbose=verbose)
                parsed_v = _parse_api_response(data_v)
                if parsed_v:
                    log_fn(f"     ✓  variante {variant}: {len(parsed_v)} chips")
                    for item in parsed_v:
                        item["strategy"]  = f"prefix_variant:{variant}"
                        item["chip_type"] = item.get("chip_type") or chip_type
                        item["subtype"]   = item.get("subtype") or subtype
                    all_results.extend(parsed_v)
                    found_any = True
                time.sleep(delay * 0.5)  # delay menor para variantes

            if not found_any:
                log_fn(f"     –  nenhuma variante retornou resultado")

        time.sleep(delay)

    log_fn(f"\n  FBGAs descobertos via prefixos: {len(all_results)}")
    return all_results


def _generate_pn_variants(prefix: str) -> list[str]:
    """
    Gera variações comuns de um prefixo de PN Micron.

    Para prefixos MT29PZZZ, MT29VZZZ, MT29TZZZ:
      - As posições seguintes codificam capacidade NAND + RAM
      - Capacidades comuns: 2G=2GB, 4G=4GB, 8G=8GB, 16G=16GB, 32G=32GB

    Para MTFC, gera variantes conhecidas de capacidade.
    """
    variants = [prefix]

    if prefix.startswith("MT29PZZZ") or prefix.startswith("MT29VZZZ") or \
       prefix.startswith("MT29TZZZ") or prefix.startswith("MT30AZZZ"):
        # Variantes de capacidade + densidade para eMCP/uMCP
        # Formato: {prefix}{ram_code}{nand_code}...
        # ram_code:  7=3GB, 8=4GB, 9=6GB, A=4GB, B=6GB, C=8GB, D=12GB, E=16GB
        # nand_code: D5=8GB (confirmado MT29TZZZ8D5/JWA60/JY941),
        #            D6=16GB (hipotético), D7=32GB, D8=64GB, D9=128GB, DA=256GB, DB=512GB
        for ram in ["7", "8", "9", "A", "B", "C", "D", "E"]:
            for nand in ["D5", "D6", "D7", "D8", "D9", "DA", "DB"]:
                variants.append(f"{prefix}{ram}{nand}")

    elif prefix.startswith("MTFC"):
        # MTFC já inclui capacidade no prefixo (MTFC4G, MTFC8G, etc.)
        # Gera sufixos comuns de packaging
        for pkg in ["AAJAM", "AACAM", "ABDAM", "AAGAM", "AADAM"]:
            variants.append(f"{prefix}{pkg}")
        variants.append(prefix)  # tenta sem sufixo também

    elif prefix.startswith("MT52") or prefix.startswith("MT53") or \
         prefix.startswith("MT62") or prefix.startswith("MT63") or \
         prefix.startswith("MT64"):
        # LPDDR: capacidades de 2, 3, 4, 6, 8, 12, 16GB
        for cap in ["02", "03", "04", "06", "08", "12", "16"]:
            variants.append(f"{prefix}{cap}")

    return variants[:50]  # limita para não gerar variantes demais


# ── Estratégia 4: Wayback CDX ─────────────────────────────────────────────────

def _sweep_wayback_cdx(
    session,
    cdx_patterns: list[str],
    delay: float,
    verbose: bool,
    log_fn,
) -> set[str]:
    """
    Consulta o índice CDX do Wayback Machine para encontrar PNs Micron
    nos caminhos de URLs de datasheets históricos (2012-2020).

    Retorna set de PN base (sem FBGA — estes serão enriquecidos via API).
    """
    discovered_pns: set[str] = set()

    log_fn("\n═══ Estratégia 4: Wayback CDX (arquivo histórico) ═══")

    CDX_API = "http://web.archive.org/cdx/search/cdx"

    for pattern in cdx_patterns:
        log_fn(f"\n  Padrão CDX: {pattern}")

        params = {
            "url":      pattern,
            "output":   "json",
            "fl":       "original,timestamp",
            "collapse": "urlkey",
            "limit":    "2000",
            "from":     "20120101",
            "to":       "20220101",
            "filter":   "statuscode:200",
        }

        # Monta URL manualmente para compatibilidade
        from urllib.parse import urlencode
        cdx_url = f"{CDX_API}?{urlencode(params)}"

        data = _api_get(cdx_url, session, verbose=verbose)

        if not data or not isinstance(data, list):
            log_fn(f"  –  sem resultados CDX")
            time.sleep(delay)
            continue

        # CDX retorna [ ["original", "timestamp"], [url1, ts1], [url2, ts2], ...]
        rows = data[1:] if data and isinstance(data[0], list) and data[0][0] == "original" else data

        pns_found = set()
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 1:
                continue
            url_str = row[0]
            # Extrai PNs Micron do path da URL
            matches = _MICRON_PN_RE.findall(url_str)
            for m in matches:
                pn_clean = m.upper().strip()
                if pn_clean.startswith(MOBILE_PREFIXES):
                    base = _extract_pn_base(pn_clean)
                    if len(base) >= 8:  # ignora prefixos muito curtos
                        pns_found.add(base)

        if pns_found:
            log_fn(f"  ✓  {len(pns_found)} PNs únicos encontrados em URLs históricas")
            if verbose:
                for pn in sorted(pns_found)[:20]:
                    log_fn(f"     {pn}")
            discovered_pns.update(pns_found)
        else:
            log_fn(f"  –  nenhum PN Micron extraído das URLs")

        time.sleep(delay)

    log_fn(f"\n  Total PNs únicos via Wayback CDX: {len(discovered_pns)}")
    return discovered_pns


# ── Persistência ──────────────────────────────────────────────────────────────

def _save_results(
    api_results: list[dict],
    wayback_pns: set[str],
    dry: bool,
    verbose: bool,
    log_fn,
) -> dict[str, int]:
    """
    Salva no banco os chips descobertos.

    - api_results (com FBGA): salva como confidence='confirmed'
    - wayback_pns (só PN, sem FBGA): salva como confidence='distributor'
      para serem enriquecidos pelo enrich_micron_fbga depois.
    """
    from chips.models import KnownPart, Brand, Source
    from django.db import transaction

    counts = {
        "enriched_created": 0,
        "enriched_skipped": 0,
        "raw_created": 0,
        "raw_skipped": 0,
        "errors": 0,
    }

    if dry:
        log_fn("\n  [DRY RUN] Não salva no banco — apenas conta")
        # Conta o que seria feito
        seen_fbgas_db = set(
            KnownPart.objects.exclude(fbga_code="").exclude(fbga_code__isnull=True)
            .values_list("fbga_code", flat=True)
        )
        seen_pns_db = set(KnownPart.objects.values_list("part_number", flat=True))

        dedup: set[str] = set()
        for item in api_results:
            fbga = item["fbga_code"]
            if fbga in seen_fbgas_db or fbga in dedup:
                counts["enriched_skipped"] += 1
            else:
                counts["enriched_created"] += 1
                dedup.add(fbga)

        for pn in wayback_pns:
            if pn in seen_pns_db:
                counts["raw_skipped"] += 1
            else:
                counts["raw_created"] += 1

        return counts

    # ── Garante que Brand e Sources existem ──────────────────────────────────
    micron_brand, _ = Brand.objects.get_or_create(
        name="Micron", defaults={"code": "MIC"}
    )
    api_source, _ = Source.objects.get_or_create(
        name="Micron FBGA API",
        defaults={"src_type": "api", "url": MICRON_FBGA_SOURCE_URL},
    )
    wayback_source, _ = Source.objects.get_or_create(
        name="Wayback Machine",
        defaults={"src_type": "scraper", "url": "https://web.archive.org"},
    )

    # ── Salva resultados com FBGA (enriched) ──────────────────────────────────
    dedup_fbgas: set[str] = set()

    for item in api_results:
        fbga    = item["fbga_code"]
        full_pn = item["part_number"]

        if fbga in dedup_fbgas:
            continue
        dedup_fbgas.add(fbga)

        try:
            with transaction.atomic():
                if KnownPart.objects.filter(fbga_code=fbga).exists():
                    counts["enriched_skipped"] += 1
                    continue

                # Infere chip_type a partir do sub-category ou da estratégia
                chip_type, subtype = _infer_chip_type(item)

                KnownPart.objects.create(
                    brand=micron_brand,
                    part_number=full_pn,
                    fbga_code=fbga,
                    chip_type=chip_type,
                    subtype=subtype,
                    confidence="confirmed",
                    source=api_source,
                    source_url=item.get("source_url", MICRON_FBGA_SOURCE_URL),
                )
                counts["enriched_created"] += 1

                if verbose:
                    log_fn(f"  [NOVO]  {fbga}  {full_pn}  ({chip_type})")

        except Exception as e:
            logger.warning("Erro ao salvar FBGA %s / PN %s: %s", fbga, full_pn, e)
            counts["errors"] += 1

    # ── Salva PNs do Wayback (raw — para enrich_micron_fbga processar) ────────
    for pn in wayback_pns:
        try:
            with transaction.atomic():
                if KnownPart.objects.filter(part_number=pn).exists():
                    counts["raw_skipped"] += 1
                    continue

                chip_type, subtype = _infer_chip_type_from_pn(pn)

                KnownPart.objects.create(
                    brand=micron_brand,
                    part_number=pn,
                    chip_type=chip_type,
                    subtype=subtype,
                    confidence="distributor",
                    source=wayback_source,
                    source_url="https://web.archive.org",
                )
                counts["raw_created"] += 1

        except Exception as e:
            logger.warning("Erro ao salvar PN Wayback %s: %s", pn, e)
            counts["errors"] += 1

    return counts


def _infer_chip_type(item: dict) -> tuple[str, str]:
    """Infere chip_type e subtype a partir dos metadados do item da API."""
    sub_cat  = item.get("sub_category", "").lower()
    strategy = item.get("strategy", "")
    chip_type_hint = item.get("chip_type", "")
    subtype_hint   = item.get("subtype", "")

    if chip_type_hint:
        return chip_type_hint, subtype_hint

    if "mcp" in sub_cat or "mcp" in strategy.lower():
        # Identifica subtype pelo LPDDR generation
        if "lpddr5" in sub_cat:  return "uMCP",  "LPDDR5"
        if "lpddr4x" in sub_cat: return "eMCP",  "LPDDR4X"
        if "lpddr4" in sub_cat:  return "eMCP",  "LPDDR4"
        if "lpddr3" in sub_cat:  return "eMCP",  "LPDDR3"
        if "lpddr2" in sub_cat:  return "eMCP",  "LPDDR2"
        return "eMCP", ""

    if "emmc" in sub_cat:
        return "eMMC", ""

    if "lpddr5" in sub_cat:  return "LPDDR", "LPDDR5"
    if "lpddr4x" in sub_cat: return "LPDDR", "LPDDR4X"
    if "lpddr4" in sub_cat:  return "LPDDR", "LPDDR4"
    if "lpddr3" in sub_cat:  return "LPDDR", "LPDDR3"
    if "lpddr2" in sub_cat:  return "LPDDR", "LPDDR2"

    # Fallback: infere do PN
    return _infer_chip_type_from_pn(item.get("part_number", ""))


def _infer_chip_type_from_pn(pn: str) -> tuple[str, str]:
    """Infere chip_type e subtype a partir do Part Number."""
    pn_up = pn.upper()

    if pn_up.startswith("MT29P") or pn_up.startswith("MT29V") or \
       pn_up.startswith("MT29T"):
        # eMCP series: MT29P=LPDDR2, MT29V=LPDDR3, MT29T=LPDDR3
        if "P" in pn_up[4:5]:  return "eMCP", "LPDDR2"
        if "V" in pn_up[4:5]:  return "eMCP", "LPDDR3"
        if "T" in pn_up[4:5]:  return "eMCP", "LPDDR3"
        return "eMCP", ""

    if pn_up.startswith("MT30A"):
        return "uMCP", "LPDDR5"

    if pn_up.startswith("MTFC") or pn_up.startswith("MTFD"):
        return "eMMC", ""

    if pn_up.startswith("MT52"):  return "LPDDR", "LPDDR3"
    if pn_up.startswith("MT53"):  return "LPDDR", "LPDDR4"
    if pn_up.startswith("MT62"):  return "LPDDR", "LPDDR4X"
    if pn_up.startswith("MT63"):  return "LPDDR", "LPDDR4X"
    if pn_up.startswith("MT64"):  return "LPDDR", "LPDDR5"

    if pn_up.startswith("MT29F"):  return "eMMC", ""  # NAND-based eMMC antigo

    return "", ""


# ── Deduplicação de resultados ────────────────────────────────────────────────

def _deduplicate(results: list[dict]) -> list[dict]:
    """Remove duplicatas por fbga_code (mantém primeira ocorrência)."""
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in results:
        fbga = item.get("fbga_code", "")
        if fbga and fbga not in seen:
            seen.add(fbga)
            deduped.append(item)
    return deduped


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Varredura massiva do catálogo Micron para coletar famílias completas "
        "de chips (eMMC, eMCP, uMCP, LPDDR2-5) mais comuns na reciclagem. "
        "Usa 4 estratégias complementares via API oficial Micron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--strategy",
            choices=["all", "subcat", "seed", "prefix", "wayback"],
            default="all",
            help=(
                "Estratégia(s) a executar:\n"
                "  all     = todas (padrão)\n"
                "  subcat  = busca por sub-categoria API\n"
                "  seed    = expansão de sementes FBGA\n"
                "  prefix  = varredura por prefixo de PN\n"
                "  wayback = Wayback CDX (arquivo histórico)\n"
            ),
        )
        parser.add_argument(
            "--delay", type=float, default=1.5, metavar="SEG",
            help="Pausa entre requests à API (padrão: 1.5s).",
        )
        parser.add_argument(
            "--limit", type=int, default=0, metavar="N",
            help="Processa no máximo N resultados por estratégia (0 = sem limite).",
        )
        parser.add_argument(
            "--no-wayback", action="store_true",
            help="Pula a estratégia Wayback CDX (mais rápido).",
        )
        parser.add_argument(
            "--seeds", nargs="+", metavar="FBGA",
            help=(
                "FBGAs adicionais para usar como sementes (além dos padrão). "
                "Ex: --seeds JW123 JY456 D9ABC"
            ),
        )
        parser.add_argument(
            "--verbose", action="store_true",
            help="Mostra status HTTP e URLs das requests (debug).",
        )

    def handle(self, *args, **options):
        dry         = options["dry_run"]
        strategy    = options["strategy"]
        delay       = options["delay"]
        limit       = options["limit"]
        skip_wayback= options["no_wayback"]
        extra_seeds = options.get("seeds") or []
        verbose     = options.get("verbose", False)

        log = self.stdout.write

        if dry:
            log(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        log(
            f"╔══════════════════════════════════════════════════════╗\n"
            f"║   collect_micron_catalog — varredura de famílias     ║\n"
            f"╚══════════════════════════════════════════════════════╝\n"
            f"Estratégia: {strategy}  |  Delay: {delay}s  |  Limit: {limit or 'sem limite'}\n"
        )

        # ── Configura sessão HTTP ─────────────────────────────────────────────
        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            log(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
                "     Para melhor bypass anti-bot: pip install curl_cffi\n"
            ))

        # ── Prepara sementes ──────────────────────────────────────────────────
        # Inclui seeds padrão + extras fornecidos via CLI + FBGAs já no banco
        seeds = list(FBGA_SEEDS)
        seeds.extend(s.upper().strip() for s in extra_seeds if s.strip())

        # Adiciona FBGAs do banco que ainda não têm família mapeada
        # (para expandir o que já temos)
        if not dry:
            try:
                from chips.models import KnownPart
                db_fbgas = list(
                    KnownPart.objects.filter(
                        brand__name="Micron",
                    ).exclude(fbga_code="").exclude(fbga_code__isnull=True)
                    .values_list("fbga_code", flat=True)[:200]  # limita para não sobrecarregar
                )
                # Adiciona do banco, priorizando sementes manuais
                seeds_set = set(seeds)
                for db_fbga in db_fbgas:
                    if db_fbga not in seeds_set:
                        seeds.append(db_fbga)
                        seeds_set.add(db_fbga)
                log(f"  Sementes: {len(FBGA_SEEDS)} fixas + {len(extra_seeds)} extras + {len(db_fbgas)} do banco\n")
            except Exception as e:
                logger.warning("Não foi possível carregar FBGAs do banco: %s", e)

        # ── Executa estratégias ───────────────────────────────────────────────
        all_api_results: list[dict] = []
        all_wayback_pns: set[str]   = set()

        if strategy in ("all", "subcat"):
            results = _sweep_subcategories(
                session=session,
                subcategories=MICRON_SUBCATEGORIES,
                delay=delay,
                verbose=verbose,
                log_fn=log,
            )
            all_api_results.extend(results)

        if strategy in ("all", "seed"):
            results = _expand_fbga_seeds(
                session=session,
                seeds=seeds,
                delay=delay,
                verbose=verbose,
                log_fn=log,
            )
            all_api_results.extend(results)

        if strategy in ("all", "prefix"):
            results = _sweep_pn_prefixes(
                session=session,
                prefixes=PN_PREFIXES,
                delay=delay,
                verbose=verbose,
                log_fn=log,
            )
            all_api_results.extend(results)

        if strategy in ("all", "wayback") and not skip_wayback:
            pns = _sweep_wayback_cdx(
                session=session,
                cdx_patterns=WAYBACK_CDX_PATTERNS,
                delay=delay,
                verbose=verbose,
                log_fn=log,
            )
            all_wayback_pns.update(pns)
        elif strategy == "wayback" and skip_wayback:
            log(self.style.WARNING("\n  ⚠  --no-wayback: estratégia Wayback pulada.\n"))

        # ── Deduplicação ──────────────────────────────────────────────────────
        all_api_results = _deduplicate(all_api_results)

        if limit:
            all_api_results = all_api_results[:limit]

        log(
            f"\n\n{'━'*55}\n"
            f"  Resultados antes de salvar:\n"
            f"  → FBGAs com PN confirmado (API Micron): {len(all_api_results)}\n"
            f"  → PNs históricos (Wayback, sem FBGA):   {len(all_wayback_pns)}\n"
        )

        if not all_api_results and not all_wayback_pns:
            log(self.style.WARNING(
                "\n⚠  Nenhum chip descoberto.\n\n"
                "Causas prováveis:\n"
                "  1. Micron mudou a estrutura da API → verifique no DevTools\n"
                "  2. Rate limiting → tente com --delay 3.0\n"
                "  3. curl_cffi não instalado → pip install curl_cffi\n"
                "  4. Conexão bloqueada → verifique firewall/VPN\n"
            ))
            return

        # ── Salva no banco ────────────────────────────────────────────────────
        log(f"\n  Salvando no banco...")
        counts = _save_results(
            api_results=all_api_results,
            wayback_pns=all_wayback_pns,
            dry=dry,
            verbose=verbose,
            log_fn=log,
        )

        # ── Relatório final ───────────────────────────────────────────────────
        log(self.style.SUCCESS(
            f"\n\n{'═'*55}\n"
            f"✅  CONCLUÍDO\n"
            f"{'═'*55}\n"
            f"  Chips com FBGA+PN criados (confidence=confirmed): {counts['enriched_created']}\n"
            f"  Chips com FBGA já existentes (pulados):           {counts['enriched_skipped']}\n"
            f"  PNs históricos criados (para enriquecer depois):  {counts['raw_created']}\n"
            f"  PNs históricos já existentes (pulados):           {counts['raw_skipped']}\n"
            f"  Erros:                                            {counts['errors']}\n"
        ))

        if counts["raw_created"] > 0 and not dry:
            log(
                f"\n  💡 Próximo passo: enriquece os PNs históricos com FBGAs oficiais:\n"
                f"     python manage.py enrich_micron_fbga\n"
            )

        if dry:
            log(self.style.WARNING("\nDry run — nenhuma alteração foi salva."))
            return

        # Invalida cache
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            log("  🗑  Cache do engine invalidado.")
        except Exception as e:
            log(self.style.WARNING(f"  ⚠  Cache não invalidado: {e}"))
