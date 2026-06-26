"""
fix_micron_capacity.py — Preenche capacidade dos chips Micron sem capacity
==========================================================================
Corrige os ~3.300 KnownParts Micron com status='enriched' e capacity vazia.

Esses registros foram criados pelo collect_micron_catalog com FBGA+PN corretos
mas sem capacity, porque a decodificação não faz parte do pipeline de coleta.

MÉTODOS DE DECODIFICAÇÃO (por família de PN):
─────────────────────────────────────────────────────────────────────────────
1. MTFC eMMC standalone
   Regex: MTFC{N}G → capacity = N GB  (trivial, 100% confiável)
   Ex: MTFC32GAPALBH → 32 GB

2. LPDDR (MT52, MT53, MT62, MT63, MT64, MT40, MT41, MT42)
   Fórmula:  capacity = N × width ÷ 8  [MB se N em M; GB se N em G]
   Regex: MT\\d+\\w+?(\\d+)(M|G)(\\d+)
   Ex: MT53E1G32D2FW → 1×32÷8 = 4 GB
       MT52L512M32D2  → 512×32÷8 MB = 2048 MB = 2 GB
       MT53B256M64D2  → 256×64÷8 MB = 2048 MB = 2 GB

3. eMCP / uMCP via DecodeMap (MT29VZZZ, MT30AZZZ — decode já existente)
   Usa a tabela MIC_MCP_CAP no banco (chave = pn[8:11]):
     7D8→3GB+64GB  AD8→4GB+64GB  AD9→4GB+128GB  BDA→6GB+256GB  etc.
   Também aplica a MT29TZZZ e MT30AZZZ que usam o mesmo esquema.

4. eMCP antigo (MT29PZZZ, MT29TZZZ — novo decode)
   Esquema diferente do MT29VZZZ:  pos8=eMMC (GB literal), pos9-10=LPDDR code
   Mapa baseado em chips confirmados da bancada + datasheets Micron:
     NAND (pos8): 4→4GB  8→8GB  (código decimal de capacidade eMMC)
     RAM  (pos9-10): D4→512MB  D5→1GB  D6→1GB  D7→2GB  D8→2GB  D9→4GB

─────────────────────────────────────────────────────────────────────────────
Para eMMC standalone (MTFC): capacity = N GB total
Para eMCP/uMCP: capacity = "NAND + RAM" (ex: "8GB+1GB")
Para LPDDR:     capacity = N GB (RAM standalone)

Uso:
    python manage.py fix_micron_capacity
    python manage.py fix_micron_capacity --dry-run
    python manage.py fix_micron_capacity --family mtfc
    python manage.py fix_micron_capacity --family lpddr
    python manage.py fix_micron_capacity --family emcp
    python manage.py fix_micron_capacity --verbose
"""

import re
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Regexes ───────────────────────────────────────────────────────────────────

# MTFC{N}G → eMMC standalone com capacidade no nome
_MTFC_RE = re.compile(r"^MTFC(\d+)G", re.IGNORECASE)

# MTFD{N}G → eMMC standalone (série mais nova)
_MTFD_RE = re.compile(r"^MTFD(\d+)G", re.IGNORECASE)

# LPDDR / DDR: extrai N (densidade) e width (largura de bus). Mesma fórmula
# (depth × width ÷ 8, SEM dies) que o engine usa no decode_density_type='micron'.
# Comando offline mantido p/ corrigir capacity de KnownParts já gravados (--overwrite).
# Formato padrão: MT53E1G32D2FW → N=1, unit=G, width=32
#                  MT52L512M32D2PF → N=512, unit=M, width=32
# Formato alternativo MT62F: MT62F1DD4EK → N=1, width=32 (assume 32-bit padrão)
_LPDDR_RE = re.compile(
    r"^MT(?:52|53|62|63|64|40|41|42)[A-Z]+?(\d+)(M|G)(\d+)",
    re.IGNORECASE,
)
# Fallback MT62Fx/MT63Fx com formato sem G/M explícito (ex: MT62F1DD4EK)
# Captura o dígito antes de "D+" (densidades como 1DD4, 2DB8, etc.)
_LPDDR_ALT_RE = re.compile(
    r"^MT(?:62|63)[A-Z]+?(\d+)D+(\d+)",
    re.IGNORECASE,
)

# PN prefixes que usam decode por fórmula (LPDDR/DDR)
LPDDR_PREFIXES = ("MT52", "MT53", "MT62", "MT63", "MT64", "MT40", "MT41", "MT42")

# PN prefixes eMCP/uMCP que usam DecodeMap MIC_MCP_CAP (mesma chave pn[8:11])
EMCP_DECODEMAP_PREFIXES = ("MT29V", "MT29T", "MT30A")

# ── Decode tables para eMCP antigo (MT29PZZZ, MT29TZZZ) ──────────────────────
#
# MT29PZZZ usa esquema diferente do MT29VZZZ:
#   pos8 = código de capacidade eMMC (dígito decimal = GB)
#   pos9-10 = código de capacidade LPDDR2
#
# Dados confirmados da bancada + datasheets:
#   MT29PZZZ8D5BKFTF → API: "72G VFBGA" = 64Gb NAND (8GB) + 8Gb RAM (1GB)
#   MT29PZZZ4D4BKESK → inferido: 32Gb NAND (4GB) + ? LPDDR2
#
# Para MT29TZZZ com chaves não cobertas pelo MIC_MCP_CAP:
#   MT29TZZZ8D5BKFAH → 8GB eMMC + 1GB LPDDR3 (confirmado: JWA60, JY941)
#   MT29TZZZ4D4BKERL → 4GB eMMC + ? LPDDR3
#
EMCP_LEGACY_NAND = {   # pos8 → eMMC GB (código decimal)
    "2": "2GB",
    "4": "4GB",
    "8": "8GB",
}
EMCP_LEGACY_RAM = {    # pos9-10 → LPDDR2/3 capacidade
    "D3": "512MB",
    "D4": "512MB",
    "D5": "1GB",
    "D6": "1GB",
    "D7": "2GB",
    "D8": "2GB",
    "D9": "4GB",
    "DA": "4GB",
}

# Prefixes que usam o esquema "legacy" (pos8=NAND decimal, pos9-10=RAM code)
EMCP_LEGACY_PREFIXES = ("MT29P",)

# MT29TZZZ pode usar qualquer um dos dois esquemas — tenta DecodMap primeiro,
# depois tenta legacy se não encontrar.


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_mtfc(pn: str) -> str | None:
    """MTFC{N}G → '{N} GB' — capacidade do eMMC standalone no nome do PN."""
    m = _MTFC_RE.match(pn)
    if m:
        return f"{m.group(1)} GB"
    m = _MTFD_RE.match(pn)
    if m:
        return f"{m.group(1)} GB"
    return None


def _decode_lpddr(pn: str) -> str | None:
    """
    LPDDR/DDR: formula N × width ÷ 8 [MB ou GB]. ⚠ O sufixo D{N} (dies) NÃO entra
    na conta — N × width já é a densidade total (ver docs/BRIEFING_MICRON_BUG_MT53_DENSIDADE.md).

    Para M (Mega):  capacity_mb = N × width ÷ 8  → converte pra GB se >= 1024
    Para G (Giga):  capacity_gb = N × width ÷ 8
    Fallback: MT62F/MT63F com formato alternativo (sem sufixo M/G explícito)

    Retorna string como '4 GB' ou '2 GB'.
    """
    m = _LPDDR_RE.match(pn)
    if m:
        n, unit, width = int(m.group(1)), m.group(2).upper(), int(m.group(3))
        if unit == "M":
            capacity_mb = n * width // 8
            if capacity_mb >= 1024 and capacity_mb % 1024 == 0:
                return f"{capacity_mb // 1024} GB"
            elif capacity_mb >= 1024:
                return f"{capacity_mb / 1024:.1f} GB"
            else:
                return f"{capacity_mb} MB"
        else:  # G
            return f"{n * width // 8} GB"

    # Fallback: MT62F/MT63F com formato "NDD{N}" (ex: MT62F1DD4EK)
    m2 = _LPDDR_ALT_RE.match(pn)
    if m2:
        n_alt = int(m2.group(1))
        # Assume 32-bit bus (padrão LPDDR4X) para capacidade aproximada
        capacity_gb = n_alt * 32 // 8
        if capacity_gb >= 1:
            return f"{capacity_gb} GB"
        return f"{n_alt * 32 * 128} MB"  # sub-GB

    return None


def _decode_emcp_decodemap(pn: str, decode_map: dict) -> str | None:
    """
    eMCP via MIC_MCP_CAP DecodeMap.
    Chave = pn[8:11] (3 chars: RAM_code + NAND_code).
    Retorna '{NAND}+{RAM}' para exibição (ex: '64GB+4GB').
    """
    if len(pn) < 11:
        return None
    key = pn[8:11].upper()
    entry = decode_map.get(key)
    if entry:
        nand, ram = entry
        return f"{nand}+{ram}"
    return None


def _decode_emcp_legacy(pn: str) -> str | None:
    """
    eMCP antigo (MT29PZZZ, parte de MT29TZZZ):
    pos8 = eMMC capacity code (4 → 4GB, 8 → 8GB)
    pos9-10 = LPDDR2/3 capacity code (D5 → 1GB, etc.)
    """
    if len(pn) < 11:
        return None

    nand_code = pn[8].upper()
    ram_code  = pn[9:11].upper()

    nand = EMCP_LEGACY_NAND.get(nand_code)
    ram  = EMCP_LEGACY_RAM.get(ram_code)

    if nand and ram:
        return f"{nand}+{ram}"
    elif nand:
        return nand  # só NAND conhecida
    return None


def _load_decode_map() -> dict:
    """
    Carrega MIC_MCP_CAP do banco.
    Retorna {key: (val_primary, val_secondary)} = {key: (nand_gb, ram_gb)}.
    """
    from chips.models import DecodeMap
    entries = DecodeMap.objects.filter(map_name="MIC_MCP_CAP").values(
        "char_key", "val_primary", "val_secondary"
    )
    return {e["char_key"]: (e["val_primary"], e["val_secondary"]) for e in entries}


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Preenche o campo capacity dos chips Micron enriched que estão sem capacidade. "
        "Usa 4 estratégias: MTFC regex, LPDDR fórmula, eMCP DecodeMap, eMCP legacy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--family",
            choices=["all", "mtfc", "lpddr", "emcp"],
            default="all",
            help="Restringe a uma família de chips (padrão: all).",
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Sobrescreve capacity mesmo em chips que já têm valor.",
        )
        parser.add_argument(
            "--verbose", action="store_true",
            help="Exibe cada chip processado.",
        )

    def handle(self, *args, **options):
        from chips.models import KnownPart

        dry      = options["dry_run"]
        family   = options["family"]
        overwrite= options["overwrite"]
        verbose  = options.get("verbose", False)

        log = self.stdout.write

        if dry:
            log(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # Carrega DecodeMap MIC_MCP_CAP uma vez
        decode_map = _load_decode_map()
        if not decode_map:
            log(self.style.WARNING(
                "  ⚠  DecodeMap MIC_MCP_CAP não encontrada no banco.\n"
                "     Execute: python manage.py populate_micron_mcp\n"
            ))

        log(f"  MIC_MCP_CAP: {len(decode_map)} chaves carregadas\n")

        # Seleciona chips sem capacidade (ou todos se --overwrite)
        qs = KnownPart.objects.filter(
            brand__name="Micron",
            status="enriched",
        ).exclude(
            fbga_code=""
        ).exclude(
            fbga_code__isnull=True
        )

        if not overwrite:
            qs = qs.filter(capacity__isnull=True) | qs.filter(capacity="")
            # Django não suporta OR diretamente em filter — usa Q objects
            from django.db.models import Q
            qs = KnownPart.objects.filter(
                brand__name="Micron",
                status="enriched",
            ).exclude(
                fbga_code=""
            ).exclude(
                fbga_code__isnull=True
            ).filter(
                Q(capacity__isnull=True) | Q(capacity="")
            )

        total = qs.count()
        log(f"  Chips Micron enriched sem capacidade: {total}\n")

        if total == 0:
            log("  ✓  Nada a fazer — todos os chips já têm capacidade.")
            return

        # ── Processa ─────────────────────────────────────────────────────────
        counts = {
            "mtfc":       {"decoded": 0, "skipped": 0},
            "lpddr":      {"decoded": 0, "skipped": 0},
            "emcp_map":   {"decoded": 0, "skipped": 0},
            "emcp_legacy":{"decoded": 0, "skipped": 0},
            "unknown":    {"decoded": 0, "skipped": 0},
        }

        updates: list[tuple[int, str]] = []  # (pk, capacity)

        for kp in qs.only("id", "part_number", "fbga_code", "chip_type", "capacity"):
            pn = (kp.part_number or "").split("-")[0].split(" ")[0].strip().upper()

            capacity = None
            method   = "unknown"

            # ── Método 1: MTFC/MTFD (eMMC standalone) ────────────────────────
            if (family in ("all", "mtfc")) and (pn.startswith("MTFC") or pn.startswith("MTFD")):
                capacity = _decode_mtfc(pn)
                method   = "mtfc"

            # ── Método 2: LPDDR / DDR ─────────────────────────────────────────
            elif (family in ("all", "lpddr")) and pn.startswith(LPDDR_PREFIXES):
                capacity = _decode_lpddr(pn)
                method   = "lpddr"

            # ── Método 3: eMCP via DecodeMap ──────────────────────────────────
            elif (family in ("all", "emcp")) and pn.startswith(EMCP_DECODEMAP_PREFIXES):
                capacity = _decode_emcp_decodemap(pn, decode_map)
                method   = "emcp_map"
                # MT29TZZZ fallback: tenta legacy se DecodeMap não cobriu
                if capacity is None and pn.startswith("MT29T"):
                    capacity = _decode_emcp_legacy(pn)
                    if capacity:
                        method = "emcp_legacy"

            # ── Método 4: eMCP legacy (MT29PZZZ) ─────────────────────────────
            elif (family in ("all", "emcp")) and pn.startswith(EMCP_LEGACY_PREFIXES):
                capacity = _decode_emcp_legacy(pn)
                method   = "emcp_legacy"

            if capacity:
                counts[method]["decoded"] += 1
                updates.append((kp.pk, capacity))
                if verbose:
                    log(f"  [{method:12s}]  {kp.fbga_code}  {pn:<35}  →  {capacity}")
            else:
                counts[method]["skipped"] += 1
                if verbose and method == "unknown":
                    log(f"  [???         ]  {kp.fbga_code}  {pn:<35}  (não decodificado)")

        # ── Salva ─────────────────────────────────────────────────────────────
        decoded_total = sum(c["decoded"] for c in counts.values())

        if not dry and updates:
            log(f"\n  Salvando {decoded_total} capacidades no banco...")
            with transaction.atomic():
                # Atualiza em lotes de 500
                batch_size = 500
                for i in range(0, len(updates), batch_size):
                    batch = updates[i:i + batch_size]
                    for pk, capacity in batch:
                        KnownPart.objects.filter(pk=pk).update(capacity=capacity)
                    log(f"    Lote {i//batch_size + 1}: {len(batch)} chips atualizados")

        # ── Relatório ─────────────────────────────────────────────────────────
        log(self.style.SUCCESS(
            f"\n\n{'═'*60}\n"
            f"✅  CONCLUÍDO\n"
            f"{'═'*60}\n"
            f"  Total chips processados:        {total}\n"
            f"  Capacidades decodificadas:      {decoded_total} ({round(decoded_total/total*100) if total else 0}%)\n"
            f"\n"
            f"  Por método:\n"
            f"  {'MTFC/MTFD (eMMC):':<30} {counts['mtfc']['decoded']:>5} decodificados  "
            f"  {counts['mtfc']['skipped']:>4} pulados\n"
            f"  {'LPDDR/DDR (fórmula):':<30} {counts['lpddr']['decoded']:>5} decodificados  "
            f"  {counts['lpddr']['skipped']:>4} pulados\n"
            f"  {'eMCP via DecodeMap:':<30} {counts['emcp_map']['decoded']:>5} decodificados  "
            f"  {counts['emcp_map']['skipped']:>4} pulados\n"
            f"  {'eMCP legacy (MT29P/T):':<30} {counts['emcp_legacy']['decoded']:>5} decodificados  "
            f"  {counts['emcp_legacy']['skipped']:>4} pulados\n"
            f"  {'Não identificados:':<30} {counts['unknown']['skipped']:>5} chips\n"
        ))

        not_decoded = total - decoded_total
        if not_decoded > 50:
            log(self.style.WARNING(
                f"\n  ℹ  {not_decoded} chips sem capacidade após este script.\n"
                f"     Para investigar, rode com --verbose e filtre os '???'.\n"
                f"     Esses chips podem ter formatos de PN não mapeados ainda.\n"
            ))

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
