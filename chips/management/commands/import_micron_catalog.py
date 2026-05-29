"""
import_micron_catalog.py — Importa e sincroniza catálogo oficial Micron via CSV
================================================================================
Lê os CSVs exportados do micron.com ("Export Full Catalog") e executa duas
operações no banco, nesta ordem:

  1. ATUALIZA registros existentes
     Para cada KnownPart Micron já no banco cujo part_number começa com o base PN
     do CSV, preenche os campos vazios: density_gbit, capacity, interface, notes.

  2. CRIA registros novos
     Para base PNs do CSV que ainda não estão no banco, consulta a API FBGA da
     Micron e cria um KnownPart por FBGA encontrado, com todos os campos preenchidos.

Mapeamento CSV → modelo KnownPart:
  TECHNOLOGY          → chip_type + subtype
  COMPONENT DENSITY   → density_gbit  (ex: "4Gb", "96Gb")
  COMPONENT DENSITY   → capacity      (convertido: "4Gb" → "512MB", "96Gb" → "12GB")
  BUS WIDTH + SPEED   → interface     (ex: "x32 @ 1866MHz")
  SPEED, VOLTAGE, PACKAGE, PIN COUNT, STATUS → notes (sumário legível)

Como obter os CSVs do catálogo Micron:
  Acesse cada página de catálogo no micron.com e clique "Export Full Catalog":
    LPDDR4:  /products/memory/lpddr-components/lpddr4/part-catalog
    LPDDR5:  /products/memory/lpddr-components/lpddr5/part-catalog
    LPDDR5X: /products/memory/lpddr-components/lpddr5x/part-catalog
    LPDDR4X: /products/memory/lpddr-components/lpddr4x/part-catalog
    LPDDR3:  /products/memory/lpddr-components/lpddr3/part-catalog
    DDR5:    /products/memory/dram-components/ddr5/part-catalog
    DDR4:    /products/memory/dram-components/ddr4/part-catalog
    eMMC:    /products/storage/managed-nand/emmc/part-catalog
    UFS:     /products/storage/managed-nand/ufs/part-catalog
    eMCP:    /products/multichip-packages/emmc-based-mcp/part-catalog
    uMCP:    /products/multichip-packages/ufs-based-mcp/part-catalog
    NAND MCP (legacy): /products/multichip-packages/nand-based-mcp/part-catalog

Quando TECHNOLOGY está em branco no CSV, o chip_type é inferido pelo nome do arquivo:
  "emmc-based-mcp"  → chip_type="eMCP"
  "ufs-based-mcp"   → chip_type="uMCP"
  "nand-based-mcp"  → chip_type="eMCP"
  "emmc"            → chip_type="eMMC"
  "ufs"             → chip_type="UFS"

Uso:
    python manage.py import_micron_catalog ~/Downloads/*.csv
    python manage.py import_micron_catalog ~/Downloads/lpddr4.csv --dry-run
    python manage.py import_micron_catalog ~/Downloads/*.csv --delay 1.5
    python manage.py import_micron_catalog ~/Downloads/*.csv --only-update
    python manage.py import_micron_catalog ~/Downloads/*.csv --only-create
"""

import csv
import re
import time
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Mapeamento TECHNOLOGY → (chip_type, subtype) ─────────────────────────────

TECH_MAP: dict[str, tuple[str, str]] = {
    # ── RAM standalone ────────────────────────────────────────────────────────
    "LPDDR4":  ("RAM", "LPDDR4"),
    "LPDDR4X": ("RAM", "LPDDR4X"),
    "LPDDR5":  ("RAM", "LPDDR5"),
    "LPDDR5X": ("RAM", "LPDDR5X"),
    "LPDDR5T": ("RAM", "LPDDR5T"),
    "LPDDR3":  ("RAM", "LPDDR3"),
    "LPDDR2":  ("RAM", "LPDDR2"),
    "DDR5":    ("RAM", "DDR5"),
    "DDR4":    ("RAM", "DDR4"),
    "DDR3":    ("RAM", "DDR3"),
    "DDR2":    ("RAM", "DDR2"),
    "GDDR6":   ("RAM", "GDDR6"),
    "GDDR5":   ("RAM", "GDDR5"),
    # ── Storage standalone ────────────────────────────────────────────────────
    # Nota: "E.MMC" normaliza para "EMMC" (remove "."), então uma entrada basta.
    # Nota: "E.MMC" normaliza para "EMMC" (remove "."), então uma entrada basta.
    "EMMC":     ("eMMC", ""),
    # eMMC standalone CSV usa "eMMC MLC" / "eMMC TLC" como TECHNOLOGY
    # Normalizados: "eMMC MLC" → "EMMCMLC", "eMMC TLC" → "EMMCTLC"
    "EMMCMLC":  ("eMMC", "MLC"),
    "EMMCTLC":  ("eMMC", "TLC"),
    "UFS":      ("UFS",  ""),
    # UFS standalone CSV (se disponível)
    "UFSTLC":   ("UFS",  "TLC"),
    "UFSQLC":   ("UFS",  "QLC"),
    # ── Multi-chip packages (MCP) — chaves já normalizadas (upper, sem espaços) ─
    # Nota: TECHNOLOGY do CSV é normalizado via .upper().replace(".", "").replace(" ", "")
    # "eMCP TLC LPDDR4"     → "EMCPTLCLPDDR4"
    # "NAND MCP SLC LPDDR4" → "NANDMCPSLCLPDDR4"
    # "NAND MCP SLC LPDDR"  → "NANDMCPSLCLPDDR"
    # "uMCP TLC LPDDR5"     → "UMCPTLCLPDDR5"
    # "uMCP TLC LPDDR4"     → "UMCPTLCLPDDR4"
    "EMCPTLCLPDDR4":    ("eMCP", "LPDDR4"),
    "NANDMCPSLCLPDDR4": ("eMCP", "LPDDR4"),
    "NANDMCPSLCLPDDR":  ("eMCP", ""),        # LPDDR versão indefinida (legacy)
    "UMCPTLCLPDDR5":    ("uMCP", "LPDDR5"),
    "UMCPTLCLPDDR4":    ("uMCP", "LPDDR4"),
    # Genéricos (fallback para variantes não mapeadas)
    "EMCP":    ("eMCP", ""),
    "UMCP":    ("uMCP", ""),
    "MCP":     ("eMCP", ""),
}

# ── Conversão COMPONENT DENSITY (Gb) → capacity legível ──────────────────────
#
# DRAM: densidade em bits → convertemos para bytes legíveis
#   4Gb  = 512MB   |  8Gb = 1GB   |  12Gb = 1.5GB  |  16Gb = 2GB
#   24Gb = 3GB     |  32Gb = 4GB  |  48Gb = 6GB    |  64Gb = 8GB
#   96Gb = 12GB    | 128Gb = 16GB
#
# Storage (eMMC/UFS/eMCP): CSV já vem em GB ("64GB"), retorna direto.
#
def _density_to_capacity(density: str) -> str:
    """Converte COMPONENT DENSITY do CSV para capacity legível."""
    if not density:
        return ""

    density = density.strip()

    # Já em GB/TB (uppercase B = bytes) → retorna direto
    # IMPORTANTE: sem re.I — "64GB" passa, "64Gb" (bits) não.
    if re.search(r'\d+\s*GB', density) or re.search(r'\d+\s*TB', density):
        return density

    # Tb (terabits, b minúsculo) → converte para Gb primeiro
    # "1Tb" = 1024 Gb = 128 GB  |  "2Tb" = 2048 Gb = 256 GB
    m_tb = re.match(r'^(\d+(?:\.\d+)?)\s*Tb\b', density)   # case-sensitive: Tb ≠ TB
    if m_tb:
        gb_val = float(m_tb.group(1)) * 1024   # 1 Tb = 1024 Gb

    else:
        # Gb (gigabits) — re.I aceita "Gb", "gb" mas não "GB" (já tratado acima)
        m_gb = re.match(r'^(\d+(?:\.\d+)?)\s*Gb\b', density, re.I)
        if not m_gb:
            return density   # formato desconhecido, retorna como está
        gb_val = float(m_gb.group(1))

    mb_val = gb_val * 128       # 1 Gb = 128 MiB (convenção binária da indústria)

    # Threshold binário: 1024 MiB = 1 GiB ≈ 1 GB
    if mb_val < 1024:
        return f"{int(mb_val)}MB"
    else:
        gb_total = mb_val / 1024
        if gb_total == int(gb_total):
            return f"{int(gb_total)}GB"
        else:
            return f"{gb_total:.1f}GB"


def _build_interface(bus_width: str, speed: str, mts: str) -> str:
    """Monta string de interface a partir dos campos do CSV."""
    parts = []
    if bus_width:
        parts.append(bus_width)
    if speed:
        parts.append(f"@ {speed}")
    if mts and mts != speed:
        parts.append(f"({mts})")
    return " ".join(parts)


def _build_notes(row: dict) -> str:
    """Monta campo notes como sumário estruturado dos campos do CSV."""
    fields = [
        ("Voltage",  row.get("I/O VOLTAGE", "")),
        ("Package",  f"{row.get('PACKAGE', '')} {row.get('PIN COUNT', '')}".strip()),
        ("Config",   row.get("COMPONENT CONFIG", "")),
        ("Protocol", row.get("PROTOCOL", "")),   # presente em uMCP CSV (UFS2.2, UFS3.1, MMC5.1)
        ("Temp",     row.get("OPERATING TEMP", "")),
        ("Status",   row.get("PART STATUS CODE", "")),
    ]
    return " | ".join(f"{k}: {v}" for k, v in fields if v)


# ── Parsing do CSV ────────────────────────────────────────────────────────────

_BASE_PN_RE = re.compile(r'^(MT[A-Z0-9]+)-')


def _extract_base_pn(full_pn: str) -> str:
    """Extrai base PN de um PN completo. Ex: MT53E1536M64D8HJ-046 AIT:B → MT53E1536M64D8HJ"""
    m = _BASE_PN_RE.match(full_pn)
    return m.group(1) if m else full_pn.split()[0]


def _read_catalog_csv(filepath: str) -> dict[str, dict]:
    """
    Lê CSV do catálogo Micron.
    Retorna dict {base_pn: info_dict} deduplicado por base_pn.
    Prefere Production > End of Life > Obsolete quando há duplicatas.
    """
    STATUS_RANK = {
        "Production": 0, "End of Life": 1, "Obsolete": 2,
        "Contact Sales": 3, "Sampling": 4,
    }

    result: dict[str, dict] = {}

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            # Remove aspas e espaços dos nomes de coluna e valores
            row = {k.strip().strip('"'): v.strip().strip('"') for k, v in raw_row.items()}

            full_pn = row.get("PART NUMBER", "").strip()
            tech    = row.get("TECHNOLOGY", "").strip().upper().replace(".", "").replace(" ", "")

            if not full_pn or not full_pn.startswith("MT"):
                continue

            base_pn = _extract_base_pn(full_pn)

            # eMMC standalone CSV usa "CAPACITY" em vez de "COMPONENT DENSITY"
            density = row.get("COMPONENT DENSITY", "").strip() or row.get("CAPACITY", "").strip()

            if tech:
                chip_type, subtype = TECH_MAP.get(tech, ("RAM", tech))
            else:
                # TECHNOLOGY em branco → infere pelo nome do arquivo
                # (ocorre em 7 linhas do ufs-based-mcp CSV)
                fname = filepath.lower()
                if "ufs-based-mcp" in fname:
                    chip_type, subtype = "uMCP", ""
                elif "emmc-based-mcp" in fname or "nand-based-mcp" in fname:
                    chip_type, subtype = "eMCP", ""
                elif "emmc" in fname:
                    chip_type, subtype = "eMMC", ""
                elif "ufs" in fname:
                    chip_type, subtype = "UFS", ""
                else:
                    chip_type, subtype = "RAM", ""

            # Override por filename: o CSV do LPDDR5X tem TECHNOLOGY="LPDDR5"
            # mas é na verdade LPDDR5X. O nome do arquivo é a fonte correta.
            fname = filepath.lower()
            if "lpddr5x" in fname and subtype == "LPDDR5":
                subtype = "LPDDR5X"
            speed     = row.get("SPEED", "").strip()
            mts       = row.get("MT/S", "").strip()
            bus_width = row.get("BUS WIDTH", "").strip()
            part_stat = row.get("PART STATUS CODE", "").strip()

            # Para eMCP/uMCP, COMPONENT DENSITY é a densidade total do package
            # (NAND + RAM combinados), NÃO a densidade de um componente DRAM.
            # Tratar como DRAM gera valores errados (ex: 544Gb → 68GB em vez de 64GB NAND).
            # A capacidade real é decodificada pelo engine via MIC_MCP_CAP (ChipFamily).
            if chip_type in ("eMCP", "uMCP"):
                cap = ""
            else:
                cap = _density_to_capacity(density)

            info = {
                "chip_type":   chip_type,
                "subtype":     subtype,
                "density_gbit": density,
                "capacity":    cap,
                "interface":   _build_interface(bus_width, speed, mts),
                "notes":       _build_notes(row),
                "part_status": part_stat,
            }

            if base_pn not in result:
                result[base_pn] = info
            else:
                # Prefere Production sobre Obsolete
                existing_rank = STATUS_RANK.get(result[base_pn]["part_status"], 99)
                new_rank      = STATUS_RANK.get(part_stat, 99)
                if new_rank < existing_rank:
                    result[base_pn] = info

    return result


# ── API FBGA (reutilizada de enrich_micron_fbga) ──────────────────────────────

_FBGA_API = (
    "https://www.micron.com/content/micron/us/en/sales-support/design-tools/"
    "fbga-parts-decoder/_jcr_content.products.json/"
    "getpartbyfbgacode/-/-/-/en_US/-/{pn}/-"
)
_FBGA_RE  = re.compile(r'^[A-Z][A-Z0-9]{4}$')
_HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder",
}
_MICRON_SOURCE_URL = "https://www.micron.com/sales-support/design-tools/fbga-parts-decoder"


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


def _query_fbga_api(pn: str, session, retries: int = 3) -> list[dict]:
    url = _FBGA_API.format(pn=pn)
    for attempt in range(retries):
        try:
            r = session.get(url, headers=_HEADERS, timeout=25)
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    return []
                return _parse_fbga_response(pn, data)
            elif r.status_code == 404:
                return []
            elif r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
        except Exception as e:
            logger.warning("Erro consultando PN %s (tentativa %d): %s", pn, attempt + 1, e)
        time.sleep(1.5 * (attempt + 1))
    return []


def _parse_fbga_response(base_pn: str, data) -> list[dict]:
    if isinstance(data, dict):
        items = data.get("details") or data.get("results") or data.get("data") or []
    elif isinstance(data, list):
        items = data
    else:
        return []

    results = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        fbga = (
            item.get("fbga-code") or item.get("fbgaCode") or item.get("fbga") or ""
        ).strip().upper()
        full_pn = (
            item.get("part-number") or item.get("partNumber") or item.get("pn") or ""
        ).strip()
        page_url = item.get("pageurl", "").strip()
        if page_url and not page_url.startswith("http"):
            page_url = f"https://www.micron.com{page_url}"

        if not fbga or not full_pn or not _FBGA_RE.match(fbga) or fbga in seen:
            continue
        seen.add(fbga)
        results.append({
            "fbga_code":   fbga,
            "part_number": full_pn,
            "source_url":  page_url or _FBGA_API.format(pn=base_pn),
        })
    return results


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Sincroniza catálogo oficial Micron (CSVs) com o banco. "
        "Atualiza campos vazios de registros existentes E cria novos via API FBGA."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_files",
            nargs="+",
            metavar="CSV",
            help="Arquivos CSV exportados do catálogo Micron.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem alterar nada.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            metavar="SEG",
            help="Pausa entre requests à API FBGA (padrão: 1.0s).",
        )
        parser.add_argument(
            "--only-update",
            action="store_true",
            help="Apenas atualiza registros existentes, não cria novos.",
        )
        parser.add_argument(
            "--only-create",
            action="store_true",
            help="Apenas cria novos registros, não atualiza existentes.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="Limita criação de novos a N base PNs (0 = sem limite).",
        )

    def handle(self, *args, **options):
        from chips.models import Brand, KnownPart, Source

        dry         = options["dry_run"]
        delay       = options["delay"]
        only_update = options["only_update"]
        only_create = options["only_create"]
        limit       = options["limit"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # ── Lê todos os CSVs ──────────────────────────────────────────────────
        catalog: dict[str, dict] = {}
        for fpath in options["csv_files"]:
            try:
                entries = _read_catalog_csv(fpath)
                self.stdout.write(
                    f"  📄 {fpath.split('/')[-1]}: {len(entries)} base PNs"
                )
                catalog.update(entries)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠  Erro em {fpath}: {e}"))

        if not catalog:
            self.stdout.write("Nenhuma entrada encontrada.")
            return

        self.stdout.write(f"\nBase PNs únicos no catálogo: {len(catalog)}\n")

        # ── Setup DB ──────────────────────────────────────────────────────────
        if not dry:
            micron_source, _ = Source.objects.get_or_create(
                name="Micron FBGA API",
                defaults={"src_type": "api", "url": _MICRON_SOURCE_URL},
            )
            micron_brand = Brand.objects.filter(name="Micron").first()
            if not micron_brand:
                micron_brand, _ = Brand.objects.get_or_create(
                    name="Micron", defaults={"code": "MIC"}
                )
        else:
            micron_source = micron_brand = None

        session = _make_session()
        if not getattr(session, "_is_cffi", False):
            self.stdout.write(self.style.WARNING(
                "  ℹ  curl_cffi não instalado — usando requests padrão.\n"
            ))

        upd_counts = {"updated": 0, "fields_filled": 0, "already_complete": 0}
        crt_counts = {"created": 0, "skipped_dup": 0, "no_results": 0, "errors": 0}

        # ════════════════════════════════════════════════════════════════════
        # PASSO 1 — ATUALIZA registros existentes
        # ════════════════════════════════════════════════════════════════════
        if not only_create:
            self.stdout.write("─" * 60)
            self.stdout.write("PASSO 1 — Atualizando registros existentes\n")

            # Carrega todos os KnownParts Micron de uma vez (evita N+1 queries)
            existing_parts = list(
                KnownPart.objects.filter(brand__name="Micron")
                .only(
                    "id", "part_number", "density_gbit", "capacity",
                    "interface", "notes", "chip_type", "subtype", "status",
                )
            )

            self.stdout.write(f"KnownParts Micron no banco: {len(existing_parts)}\n")

            for kp in existing_parts:
                base_pn = _extract_base_pn(kp.part_number)
                info = catalog.get(base_pn)
                if not info:
                    continue

                # Campos a atualizar (só preenche se estiver vazio)
                update_fields: list[str] = []

                def _maybe_update(field: str, new_val: str):
                    if new_val and not getattr(kp, field):
                        setattr(kp, field, new_val)
                        update_fields.append(field)

                _maybe_update("density_gbit", info["density_gbit"])
                _maybe_update("capacity",     info["capacity"])
                _maybe_update("interface",    info["interface"])
                _maybe_update("notes",        info["notes"])
                # Garante chip_type/subtype se estiver vazio
                _maybe_update("chip_type",    info["chip_type"])
                _maybe_update("subtype",      info["subtype"])

                if not update_fields:
                    upd_counts["already_complete"] += 1
                    continue

                fields_str = ", ".join(update_fields)
                if dry:
                    self.stdout.write(
                        f"  [UPDATE] {kp.part_number[:45]:45s}  ← {fields_str}"
                    )
                    upd_counts["updated"] += 1
                    upd_counts["fields_filled"] += len(update_fields)
                    continue

                try:
                    update_fields.append("last_updated")
                    kp.save(update_fields=update_fields)
                    upd_counts["updated"] += 1
                    upd_counts["fields_filled"] += len(update_fields) - 1  # -1 para last_updated
                except Exception as e:
                    logger.warning("Erro ao atualizar %s: %s", kp.part_number, e)

            self.stdout.write(self.style.SUCCESS(
                f"\n  Registros atualizados:   {upd_counts['updated']}\n"
                f"  Campos preenchidos:      {upd_counts['fields_filled']}\n"
                f"  Já completos (pulados):  {upd_counts['already_complete']}\n"
            ))

        # ════════════════════════════════════════════════════════════════════
        # PASSO 2 — CRIA novos registros
        # ════════════════════════════════════════════════════════════════════
        if not only_update:
            self.stdout.write("─" * 60)
            self.stdout.write("PASSO 2 — Criando novos registros via API FBGA\n")

            # Base PNs que já têm ao menos um KnownPart no banco
            all_existing_pns = set(
                KnownPart.objects.filter(brand__name="Micron")
                .values_list("part_number", flat=True)
            )
            covered_bases: set[str] = set()
            for pn in all_existing_pns:
                covered_bases.add(_extract_base_pn(pn))

            new_bases = {
                bp: info for bp, info in catalog.items()
                if bp not in covered_bases
            }

            self.stdout.write(f"Base PNs já cobertos no banco: {len(covered_bases & catalog.keys())}")
            self.stdout.write(f"Base PNs novos a criar:        {len(new_bases)}\n")

            items = list(new_bases.items())
            if limit:
                items = items[:limit]
                self.stdout.write(f"(limitado a {limit} base PNs)\n")

            total = len(items)
            for idx, (base_pn, info) in enumerate(items, 1):
                self.stdout.write(
                    f"[{idx}/{total}] {base_pn:28s} {info['chip_type']} "
                    f"{info['subtype']:10s} {info['density_gbit']:6s} ... ",
                    ending="",
                )
                self.stdout.flush()

                fbga_results = _query_fbga_api(base_pn, session)

                if not fbga_results:
                    self.stdout.write(self.style.WARNING("sem resultados na API"))
                    crt_counts["no_results"] += 1
                    time.sleep(delay)
                    continue

                self.stdout.write(self.style.SUCCESS(f"{len(fbga_results)} FBGAs"))

                for item in fbga_results:
                    fbga    = item["fbga_code"]
                    full_pn = item["part_number"]
                    src_url = item["source_url"]

                    # Guarda: a API Micron pode retornar dies emparelhados
                    # (ex: LPDDR4 die MT53B quando consultado um base PN eMMC/MCP).
                    # Só criamos registros cujo base PN retornado bate com o consultado.
                    returned_base = _extract_base_pn(full_pn)
                    if returned_base != base_pn:
                        logger.debug(
                            "Ignorando PN cross-family: consultado=%s retornou=%s (%s)",
                            base_pn, returned_base, full_pn,
                        )
                        continue

                    if dry:
                        self.stdout.write(
                            f"   {fbga}  →  {full_pn}"
                            f"  [{info['capacity']}]  [{info['interface']}]"
                        )
                        crt_counts["created"] += 1
                        continue

                    try:
                        with transaction.atomic():
                            if KnownPart.objects.filter(fbga_code=fbga).exists():
                                crt_counts["skipped_dup"] += 1
                                continue
                            KnownPart.objects.create(
                                brand=micron_brand,
                                part_number=full_pn,
                                fbga_code=fbga,
                                chip_type=info["chip_type"],
                                subtype=info["subtype"],
                                density_gbit=info["density_gbit"],
                                capacity=info["capacity"],
                                interface=info["interface"],
                                notes=info["notes"],
                                status="enriched",
                                confidence="confirmed",
                                source=micron_source,
                                source_url=src_url,
                            )
                            crt_counts["created"] += 1
                    except Exception as e:
                        logger.warning("Erro ao criar %s / %s: %s", full_pn, fbga, e)
                        crt_counts["errors"] += 1

                time.sleep(delay)

            self.stdout.write(self.style.SUCCESS(
                f"\n  KnownParts criados:              {crt_counts['created']}\n"
                f"  FBGAs já existentes (pulados):   {crt_counts['skipped_dup']}\n"
                f"  Base PNs sem resultado na API:   {crt_counts['no_results']}\n"
                f"  Erros:                           {crt_counts['errors']}\n"
            ))

        # ── Relatório final ───────────────────────────────────────────────────
        self.stdout.write("─" * 60)
        if dry:
            self.stdout.write(self.style.WARNING("Dry run — nenhuma alteração salva."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"✅  Concluído.\n"
            f"   Registros atualizados:  {upd_counts.get('updated', 0)}\n"
            f"   Novos KnownParts:       {crt_counts.get('created', 0)}\n"
        ))

        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))
