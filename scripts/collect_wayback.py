"""
collect_wayback.py — Stage 5 (último recurso): coleta via Wayback Machine
=========================================================================
Usa a CDX API gratuita do Internet Archive para encontrar snapshots históricos
de páginas com chips Micron, especialmente de 2015–2021 (era dos chips alvo).

Estratégia de busca:
  1. Snapshots de páginas de produto Micron (micron.com/products/*)
  2. Snapshots de páginas de distribuidores com listagens Micron:
       - preduo.com/emcp/, /ufs/, /emmc/, etc.
       - farnell.com com Micron
       - digikey.com com Micron
       - mouser.com com Micron
  3. Snapshots de catálogos de reciclagem/estoque de chips

Para cada snapshot encontrado, baixa o HTML arquivado e extrai:
  - Part Numbers Micron (MT*, D9*)
  - FBGA codes (5 chars alfanuméricos)

Salva com confidence='estimated' — sinal de que requer verificação.
Chips com confidence=estimated NÃO são exibidos na UI de triagem até
confirmação manual.

CDX API: https://web.archive.org/cdx/search/cdx
  Documentação: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

Uso:
    python scripts/collect_wayback.py
    python scripts/collect_wayback.py --dry-run
    python scripts/collect_wayback.py --years 2015-2021
    python scripts/collect_wayback.py --source micron          # só site Micron
    python scripts/collect_wayback.py --source preduo          # só Preduo arquivado
    python scripts/collect_wayback.py --source distributors    # Farnell/DigiKey/Mouser
    python scripts/collect_wayback.py --limit 500 --delay 2
    python scripts/collect_wayback.py --fbga-only              # só chips com FBGA encontrado
"""

import os
import re
import sys
import time
import json
import argparse
import logging
from pathlib import Path
from urllib.parse import quote

# ── Setup Django ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# CDX API endpoint
CDX_API = "https://web.archive.org/cdx/search/cdx"

# Wayback Machine URL para acessar snapshot
WAYBACK_URL = "https://web.archive.org/web/{timestamp}/{url}"

# Padrão PN Micron
_PN_RE = re.compile(
    r"\b(MT[0-9]{2}[A-Z0-9]{5,}|D9[A-Z0-9]{3,}|NW[A-Z0-9]{3,})\b",
    re.IGNORECASE,
)

# FBGA code Micron: começa com J (eMMC/eMCP) ou D9 (DRAM móvel)
_FBGA_RE = re.compile(r"\b([JD][A-Z0-9]{4})\b")
_FBGA_STRICT_RE = re.compile(r"^[A-Z0-9]{5}$")

# Fontes de busca e seus padrões de URL para CDX API.
#
# IMPORTANTE: a CDX API precisa de URLs com scheme (http:// ou https://).
# Wildcards: * no final = prefixo; * no meio = NÃO suportado pela CDX.
# Use matchType=prefix (padrão) ou matchType=domain para domínio inteiro.
#
# Preduo (preduo.com) está pouco arquivado — use "micron" ou "distributors"
# para melhores resultados. Preduo usa --years 2019-2023.
#
SEARCH_SOURCES = {
    # ── Nota sobre o site da Micron ──────────────────────────────────────────
    # micron.com é uma SPA React desde ~2018 — o HTML arquivado no Wayback
    # NÃO contém dados de chip (estão no JS/API). Use "distributors" para
    # páginas com HTML estático rico em dados.
    # Exceção: PDFs de datasheets e documentos técnicos arquivados são estáticos.
    "micron": [
        # Documentos/PDFs da Micron arquivados (HTML de referência de produto)
        "https://www.micron.com/support/part-information/",
        "https://www.micron.com/products/mobile-storage-and-computing/",
        # Site legado Micron (~2015-2017, antes da migração para SPA)
        # Nesse período as páginas tinham tabelas estáticas com PNs
        "http://www.micron.com/products/mobile-storage-and-computing/emmc-based-mcp/",
        "http://www.micron.com/products/managed-nand/emmc/",
        "http://www.micron.com/~/media/documents/products/",
    ],
    "preduo": [
        # Preduo está pouco arquivado — pode retornar 0 resultados.
        # Se retornar 0, use --source distributors (DigiKey/Farnell têm cobertura real).
        "https://www.preduo.com/list/emcp",
        "https://www.preduo.com/list/umcp",
        "https://www.preduo.com/list/emmc",
        "https://www.preduo.com/list/ufs",
        "http://www.preduo.com/",
    ],
    "distributors": [
        # ── DigiKey — eMCP/eMMC específico ──────────────────────────────────
        # Produto individual Micron eMCP (página de detalhe — tem specs + FBGA)
        "https://www.digikey.com/product-detail/en/micron-technology-inc/MT29VZZZAD8GQFSL-046-WT/",
        "https://www.digikey.com/product-detail/en/micron-technology-inc/MT29VZZZBD9GQFSL-046-WT/",
        # Categoria embedded flash / managed NAND (mais específica que memory/774)
        # Categoria 517 = Embedded — Flash (eMCP, eMMC)
        "https://www.digikey.com/products/en/integrated-circuits-ics/embedded/517",
        # Categoria 774 = Memory (genérica — captura NAND, NOR, DRAM também)
        # Usar com --mobile-only para filtrar
        "https://www.digikey.com/products/en/integrated-circuits-ics/memory/774",
        "https://www.digikey.com/en/products/filter/memory/774",
        # ── Farnell / Element14 — boas listagens Micron eMCP ─────────────────
        "https://www.farnell.com/search/?st=MT29V",
        "https://uk.farnell.com/search?st=micron+emcp",
        "https://www.farnell.com/search/?st=MT29T",
        "https://uk.farnell.com/search?st=micron+emmc",
        # ── Mouser — static product listings com specs ────────────────────────
        "https://www.mouser.com/Micron-Technology/Semiconductors/Memory-ICs/",
        "https://www.mouser.com/c/semiconductors/memory-ics/?manufacturer=Micron%20Technology",
        # ── Future Electronics — distribuidora B2B, boa cobertura Micron MCP ─
        "https://www.futureelectronics.com/search?term=MT29VZZZ",
        "https://www.futureelectronics.com/search?term=MTFC",
    ],
}

# Prefixos de PN que indicam chips relevantes para reciclagem de smartphones.
# Usado com --mobile-only para filtrar chips não-móveis (NAND raw, NOR, DDR4 etc.)
MOBILE_PREFIXES = (
    "MT29VZZZ",  # eMCP LPDDR4
    "MT29TZZZ",  # eMCP LPDDR3 (geração anterior)
    "MT30AZZZ",  # uMCP LPDDR5
    "MTFC",      # eMMC (iNAND)
    "MTFD",      # eMMC industrial
    "MT29P",     # UFS
    "MT53",      # LPDDR4/5 (MT53B, MT53D, MT53E)
    "MT52",      # LPDDR3 (MT52L, MT52F)
    "MT62",      # LPDDR5X
    "MT63",      # LPDDR5
    "MT64",      # LPDDR5
)

# Tipos de chip inferidos do PN para persistence
def _infer_chip_type(pn: str) -> tuple[str, str]:
    """
    Convenção de prefixos Micron:
      MT29VZZZ* → eMCP LPDDR4    MT30AZZZ* → uMCP LPDDR5
      MTFC*/MTFD* → eMMC (iNAND) MT29P*    → UFS
      MT53B/D/E*  → LPDDR4       MT62-64*  → LPDDR5
      MT52L/F*    → LPDDR3       MT29F/S*  → NAND (raw, NÃO eMMC)
      D9xxx       → DRAM mobile
    """
    pn = pn.upper()
    if pn.startswith("MT29VZZZ"):         return ("eMCP",  "LPDDR4")
    if pn.startswith("MT30AZZZ"):         return ("uMCP",  "LPDDR5")
    if re.match(r"MT[FC][A-Z]",    pn):  return ("eMMC",  "")        # MTFC*, MTFD*
    if pn.startswith("MT29P"):            return ("UFS",   "")
    if re.match(r"MT53[BDED]",     pn):  return ("DRAM",  "LPDDR4")
    if re.match(r"MT6[2-4]",       pn):  return ("DRAM",  "LPDDR5")
    if re.match(r"MT52[LF]",       pn):  return ("DRAM",  "LPDDR3")
    if re.match(r"MT29[FS]",       pn):  return ("NAND",  "")
    if re.match(r"D9[A-Z0-9]{3}",  pn):  return ("DRAM",  "")
    return ("Flash", "")


# ── HTTP session ──────────────────────────────────────────────────────────────

def _make_session():
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


def _get(session, url: str, timeout: int = 20, params: dict = None):
    """GET com retry simples."""
    headers = {
        "User-Agent": "Mozilla/5.0 WhatTheChip-collector/1.0 (+recycling research)",
    }
    for attempt in range(3):
        try:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                wait = 10 * (attempt + 1)
                logger.warning("Rate limit (HTTP %s) — aguardando %ds", r.status_code, wait)
                time.sleep(wait)
                continue
            if r.status_code == 404:
                return None
            logger.debug("HTTP %s: %s", r.status_code, url)
        except Exception as e:
            logger.debug("Erro (tentativa %d/3): %s — %s", attempt + 1, e, url)
            time.sleep(3)
    return None


# ── CDX API ───────────────────────────────────────────────────────────────────

def cdx_query(
    session,
    url_pattern: str,
    from_year: int,
    to_year:   int,
    limit:     int = 500,
    collapse:  str = "urlkey",   # deduplication
) -> list[dict]:
    """
    Consulta a CDX API para encontrar snapshots arquivados.
    Retorna lista de dicts com: url, timestamp, status.
    """
    params = {
        "url":       url_pattern,
        "matchType": "prefix",    # busca por prefixo de URL (mais resultados)
        "output":    "json",
        "fl":        "timestamp,statuscode,original",
        "filter":    "statuscode:200",
        "from":      f"{from_year}0101",
        "to":        f"{to_year}1231",
        "limit":     str(limit),
        "collapse":  collapse,
    }

    r = _get(session, CDX_API, timeout=30, params=params)
    if r is None:
        return []

    try:
        rows = r.json()
    except Exception:
        logger.warning("CDX retornou JSON inválido para: %s", url_pattern)
        return []

    # Primeira linha é cabeçalho
    if not rows or len(rows) < 2:
        return []

    header = rows[0]
    results = []
    for row in rows[1:]:
        if len(row) >= len(header):
            results.append(dict(zip(header, row)))

    return results


# ── Extração de chips do HTML arquivado ──────────────────────────────────────

def extract_chips_from_html(html: str, source_url: str) -> list[dict]:
    """
    Extrai Part Numbers e FBGA codes do HTML de uma página arquivada.
    Retorna lista de dicts: {part_number, fbga_code, source_url}
    """
    results: list[dict] = []
    seen_pns: set[str] = set()

    # Remove tags HTML para trabalhar com texto limpo
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)  # entidades HTML

    lines = text.splitlines()
    for i, line in enumerate(lines):
        pn_match = _PN_RE.search(line)
        if not pn_match:
            continue

        pn = pn_match.group(0).upper()
        if pn in seen_pns:
            continue

        # Procura FBGA nas linhas próximas
        fbga = ""
        context = " ".join(lines[max(0, i-1):min(len(lines), i+4)])
        for m in _FBGA_RE.finditer(context):
            candidate = m.group(0)
            if _FBGA_STRICT_RE.match(candidate) and candidate[0] in "JDN":
                fbga = candidate
                break

        seen_pns.add(pn)
        results.append({
            "part_number": pn,
            "fbga_code":   fbga,
            "source_url":  source_url,
        })

    return results


# ── Persistência ──────────────────────────────────────────────────────────────

def save_to_db(
    chips: list[dict],
    dry: bool,
    overwrite: bool,
    fbga_only: bool,
) -> dict[str, int]:
    from chips.models import Brand, KnownPart, Source

    CONFIDENCE_ORDER = {
        "confirmed": 0, "manual": 1, "distributor": 2,
        "estimated": 3,
    }
    MY_CONFIDENCE      = "estimated"
    MY_CONFIDENCE_RANK = CONFIDENCE_ORDER[MY_CONFIDENCE]

    counts = {"created": 0, "updated": 0, "skipped": 0, "no_fbga_skipped": 0}

    if dry:
        wayback_src  = None
        micron_brand = None
    else:
        micron_brand, _ = Brand.objects.get_or_create(
            name="Micron", defaults={"code": "MIC"}
        )
        wayback_src, _ = Source.objects.get_or_create(
            name="Wayback Machine",
            defaults={"src_type": "archive", "url": "https://web.archive.org"},
        )

    for chip in chips:
        pn   = chip["part_number"]
        fbga = chip.get("fbga_code", "") or ""

        if fbga_only and not fbga:
            counts["no_fbga_skipped"] += 1
            continue

        chip_type, subtype = _infer_chip_type(pn)
        src_url = chip.get("source_url", "")

        if dry:
            exists = KnownPart.objects.filter(part_number=pn).exists()
            action = "UPDATE" if (exists and overwrite) else ("SKIP" if exists else "CREATE")
            if action != "SKIP":
                print(
                    f"  [{action:6s}] {pn:40s}  fbga={fbga or '-':6s}  "
                    f"{chip_type}" + (f" {subtype}" if subtype else "")
                )
            counts["created" if action == "CREATE" else
                   "updated" if action == "UPDATE" else "skipped"] += 1
            continue

        try:
            existing = KnownPart.objects.filter(part_number=pn).first()

            if existing is None:
                KnownPart.objects.create(
                    brand=micron_brand,
                    part_number=pn,
                    fbga_code=fbga,
                    chip_type=chip_type,
                    subtype=subtype,
                    confidence=MY_CONFIDENCE,
                    source=wayback_src,
                    source_url=src_url,
                    notes="Fonte: Wayback Machine — verificar antes de confiar.",
                )
                counts["created"] += 1

            elif overwrite:
                existing_rank = CONFIDENCE_ORDER.get(existing.confidence, 99)
                if existing_rank >= MY_CONFIDENCE_RANK:
                    update_fields: list[str] = []
                    # Wayback só preenche campos vazios (nunca downgrade de confidence)
                    if fbga and not existing.fbga_code:
                        existing.fbga_code = fbga
                        update_fields.append("fbga_code")
                    if not existing.chip_type and chip_type:
                        existing.chip_type = chip_type
                        update_fields.append("chip_type")
                    if update_fields:
                        update_fields.append("last_updated")
                        existing.save(update_fields=update_fields)
                        counts["updated"] += 1
                    else:
                        counts["skipped"] += 1
                else:
                    counts["skipped"] += 1
            else:
                counts["skipped"] += 1

        except Exception as e:
            logger.warning("Erro ao salvar %s: %s", pn, e)

    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5 (último recurso): coleta chips Micron via Wayback Machine."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria feito sem salvar.")
    parser.add_argument("--years", default="2015-2021", metavar="AAAA-AAAA",
                        help="Período de busca (padrão: 2015-2021).")
    parser.add_argument("--source",
                        choices=list(SEARCH_SOURCES.keys()) + ["all"],
                        default="micron",
                        help="Fonte(s) a buscar (padrão: micron).")
    parser.add_argument("--limit", type=int, default=200, metavar="N",
                        help="Limite de snapshots por padrão de URL (padrão: 200).")
    parser.add_argument("--delay", type=float, default=2.0, metavar="SEG",
                        help="Pausa em segundos entre requests (padrão: 2.0).")
    parser.add_argument("--overwrite", action="store_true",
                        help="Atualiza campos vazios em KnownParts existentes.")
    parser.add_argument("--fbga-only", action="store_true",
                        help="Salva apenas chips onde FBGA code foi encontrado.")
    parser.add_argument("--mobile-only", action="store_true",
                        help=(
                            "Filtra apenas chips relevantes para reciclagem de smartphones "
                            "(eMCP, eMMC, LPDDR, UFS). Descarta NAND raw, NOR, DDR4 etc. "
                            "Recomendado quando usando --source distributors."
                        ))
    parser.add_argument("--max-pages", type=int, default=20, metavar="N",
                        help="Máximo de snapshots a processar por padrão de URL (padrão: 20).")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        print("⚠  DRY RUN — nenhuma alteração será salva.\n")

    # Parseia período de anos
    try:
        year_parts = args.years.split("-")
        from_year  = int(year_parts[0])
        to_year    = int(year_parts[1]) if len(year_parts) > 1 else from_year
    except (ValueError, IndexError):
        print(f"❌  Formato de anos inválido: {args.years}  (esperado: AAAA-AAAA)")
        sys.exit(1)

    print(f"Período: {from_year}–{to_year}")
    print(f"Fonte(s): {args.source}")

    session = _make_session()

    # Seleciona padrões de URL a buscar
    if args.source == "all":
        patterns: list[tuple[str, str]] = []
        for src_name, src_patterns in SEARCH_SOURCES.items():
            for p in src_patterns:
                patterns.append((src_name, p))
    else:
        patterns = [(args.source, p) for p in SEARCH_SOURCES[args.source]]

    print(f"Total de padrões CDX: {len(patterns)}\n")

    # ── CDX query + download + extração ──────────────────────────────────────
    all_chips: list[dict] = []
    seen_pns:  set[str]   = set()

    for src_name, url_pattern in patterns:
        print(f"\n▶  [{src_name}] {url_pattern}")

        snapshots = cdx_query(
            session,
            url_pattern=url_pattern,
            from_year=from_year,
            to_year=to_year,
            limit=args.limit,
        )
        print(f"  Snapshots encontrados: {len(snapshots)}")

        if not snapshots:
            time.sleep(args.delay)
            continue

        # Processa um subset dos snapshots (evita sobrecarga no Wayback)
        to_process = snapshots[:args.max_pages]
        print(f"  Processando: {len(to_process)} snapshots")

        for snap in to_process:
            timestamp  = snap.get("timestamp", "")
            original   = snap.get("original", "")
            if not timestamp or not original:
                continue

            wb_url = WAYBACK_URL.format(timestamp=timestamp, url=original)
            logger.debug("Fetching: %s", wb_url)

            r = _get(session, wb_url, timeout=25)
            if r is None:
                time.sleep(args.delay)
                continue

            html = r.text
            chips = extract_chips_from_html(html, source_url=wb_url)

            # Filtra novos
            new_chips = [c for c in chips if c["part_number"] not in seen_pns]

            # Filtra chips móveis se --mobile-only
            if args.mobile_only:
                before = len(new_chips)
                new_chips = [
                    c for c in new_chips
                    if c["part_number"].upper().startswith(MOBILE_PREFIXES)
                ]
                dropped = before - len(new_chips)
                if dropped:
                    logger.debug("--mobile-only: descartados %d chips não-móveis", dropped)

            for c in new_chips:
                seen_pns.add(c["part_number"])

            if new_chips:
                print(f"  {timestamp[:8]}: {len(new_chips)} PNs novos extraídos")
            all_chips.extend(new_chips)

            time.sleep(args.delay)

        time.sleep(args.delay)

    print(f"\n\nTotal de chips únicos coletados: {len(all_chips)}")

    if not all_chips:
        print("\n⚠  Nenhum chip encontrado no Wayback Machine para o período especificado.")
        print("   Sugestões:")
        print("   • Tente um período mais amplo: --years 2013-2023")
        print("   • Aumente --limit e --max-pages")
        print("   • Use --source micron para focar no site oficial arquivado")
        return

    # ── Salva no banco ────────────────────────────────────────────────────────
    print(f"\nSalvando no banco (fbga_only={args.fbga_only}) ...")
    counts = save_to_db(
        chips=all_chips,
        dry=dry,
        overwrite=args.overwrite,
        fbga_only=args.fbga_only,
    )

    print(
        f"\n{'[DRY RUN] ' if dry else ''}Resultado:\n"
        f"  Criados:                  {counts['created']}\n"
        f"  Atualizados (sem FBGA):   {counts['updated']}\n"
        f"  Pulados (já existiam):    {counts['skipped']}\n"
        f"  Sem FBGA (--fbga-only):   {counts.get('no_fbga_skipped', 0)}\n"
    )

    if dry:
        print("⚠  DRY RUN — nenhuma alteração foi salva.")
        return

    # Invalida cache do engine
    try:
        from chips.engine import clear_engine_cache
        clear_engine_cache()
        print("🗑  Cache do engine invalidado.")
    except Exception as e:
        print(f"⚠  Cache não invalidado: {e}")

    print(
        "\n💡 Chips com confidence='estimated' (Wayback) requerem verificação manual.\n"
        "   Use o admin do Django para revisar: /admin/chips/knownpart/"
        "?confidence=estimated"
    )


if __name__ == "__main__":
    main()
