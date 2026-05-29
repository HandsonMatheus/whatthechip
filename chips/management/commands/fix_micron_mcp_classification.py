"""
fix_micron_mcp_classification.py
=================================
Corrige chip_type de KnownParts Micron MCP (MT29VZZZ, MT29TZZZ) determinando
se cada chip é eMMC-based (eMCP) ou UFS-based (uMCP).

PROBLEMA
--------
A família MT29VZZZ cobre dois tipos fisicamente distintos de chips:
  - emmc-based-mcp → eMCP: NAND eMMC + LPDDR4 (bancada eMMC)
  - ufs-based-mcp  → uMCP: NAND UFS  + LPDDR4 (bancada UFS)

O script enrich_micron_fbga.py copia chip_type da família base ("eMCP") para
TODOS os registros enriquecidos, mesmo para chips UFS. O resultado é que chips
UFS aparecem como "eMCP" no banco, o que pode levar a roteamento incorreto na
bancada de reciclagem.

SOLUÇÃO (duas fontes, em ordem de prioridade)
---------------------------------------------
1. source_url com URL de produto Micron (pageurl da API):
   "...ufs-based-mcp..."  → chip_type = "uMCP"
   "...emmc-based-mcp..." → chip_type = "eMCP"

2. Fallback por decode do PN (quando source_url é a URL genérica da API FBGA):
   MT29VZZZ: posição 11 do PN limpo → F=UFS (uMCP), G=eMMC (eMCP)
   MT29TZZZ: sempre eMCP (família eMMC 4.x/5.0 + LPDDR3)

   Convenção oficial Micron (ordering guide MT29VZZZ):
     MT29VZZZ[AD8][F]QFSL → F em pn[11] = UFS 2.2 (uMCP)
     MT29VZZZ[AD8][G]QFSL → G em pn[11] = eMMC 5.1 (eMCP)

NOTA: O campo emcp_nand NÃO é alterado por este script. A correção da interface
no resultado de classificação é feita pelo engine via BUG-3 fix (source_url).

COBERTURA
---------
  - MT29VZZZ (eMMC 5.1 / UFS 2.2 + LPDDR4)
  - MT29TZZZ (eMMC 4.x/5.0 + LPDDR3 — sempre eMCP)
  - MT30AZZZ não precisa: já tem chip_type="uMCP" e interface="UFS 3.1" corretos

Uso:
    python manage.py fix_micron_mcp_classification
    python manage.py fix_micron_mcp_classification --dry-run
    python manage.py fix_micron_mcp_classification --verbose
"""

import logging
import re

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# Prefixos de família MCP Micron que podem ter chips UFS misclassificados
MCP_PREFIXES = ("MT29VZZZ", "MT29TZZZ")


def _correct_type_from_pn(pn: str) -> str | None:
    """
    Fallback: determina chip_type correto pelo decode do PN quando source_url
    não contém a categoria do produto.

    MT29VZZZ: posição 11 (0-indexed) do PN limpo distingue UFS de eMMC:
      F → uMCP (UFS 2.2 + LPDDR4)
      G → eMCP (eMMC 5.1 + LPDDR4)

    MT29TZZZ: sempre eMCP (família eMMC 4.x/5.0 + LPDDR3, sem variante UFS).

    Retorna "uMCP", "eMCP" ou None se não for possível determinar.
    """
    pn_upper = pn.upper()
    pn_clean = re.sub(r'[^A-Z0-9]', '', pn_upper)

    if pn_clean.startswith("MT29VZZZ"):
        if len(pn_clean) > 11:
            c = pn_clean[11]
            if c == 'F':
                return "uMCP"
            elif c == 'G':
                return "eMCP"
        # Posição 11 não encontrada ou char desconhecido — não inferir
        return None

    if pn_clean.startswith("MT29TZZZ"):
        # MT29TZZZ é exclusivamente eMMC 4.x/5.0 + LPDDR3 (sem variante UFS)
        return "eMCP"

    return None


class Command(BaseCommand):
    help = (
        "Corrige chip_type de KnownParts Micron MCP (MT29VZZZ, MT29TZZZ). "
        "Fonte 1: source_url com URL de produto (ufs-based-mcp → uMCP, emmc-based-mcp → eMCP). "
        "Fonte 2 (fallback): decode do PN — MT29VZZZ pn[11] F=uMCP, G=eMCP."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem alterar o banco.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Lista cada chip corrigido.",
        )

    def handle(self, *args, **options):
        from chips.models import KnownPart

        dry     = options["dry_run"]
        verbose = options["verbose"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        # ── Seleciona candidatos ──────────────────────────────────────────────
        # Todos os chips confirmados das famílias MCP Micron (com ou sem source_url).
        # Chips sem source_url também são cobertos pelo fallback de decode do PN.
        from django.db.models import Q

        prefix_q = Q()
        for pf in MCP_PREFIXES:
            prefix_q |= Q(part_number__startswith=pf)

        qs = KnownPart.objects.filter(
            prefix_q,
            status="enriched",
            confidence="confirmed",
        )

        total = qs.count()
        self.stdout.write(f"KnownParts MCP Micron confirmados: {total}\n")

        if total == 0:
            self.stdout.write("Nada a processar.")
            return

        counts = {
            "ufs_fixed":    0,   # chip_type atualizado para uMCP
            "emmc_fixed":   0,   # chip_type atualizado para eMCP
            "already_ok":   0,   # chip_type já estava correto
            "url_source":   0,   # tipo determinado via source_url (produto Micron)
            "pn_source":    0,   # tipo determinado via decode do PN (fallback)
            "no_decode":    0,   # não foi possível determinar o tipo
            "errors":       0,
        }

        for kp in qs.iterator():
            src = kp.source_url or ""

            # ── Fonte 1: URL do produto Micron ────────────────────────────────
            # enrich_micron_fbga.py armazena o pageurl da API quando disponível,
            # que contém o caminho da categoria (ufs-based-mcp ou emmc-based-mcp).
            if "ufs-based-mcp" in src:
                correct_type = "uMCP"
                source_tag   = "url"
            elif "emmc-based-mcp" in src:
                correct_type = "eMCP"
                source_tag   = "url"
            else:
                # ── Fonte 2: Decode do PN (fallback) ─────────────────────────
                # source_url é a URL genérica da API FBGA (não contém categoria).
                # Usa a convenção oficial Micron: MT29VZZZ pn[11] F=UFS, G=eMMC.
                correct_type = _correct_type_from_pn(kp.part_number)
                source_tag   = "pn"
                if not correct_type:
                    counts["no_decode"] += 1
                    if verbose:
                        self.stdout.write(
                            f"  {kp.fbga_code or '-----'}  {kp.part_number[:48]:<48}  "
                            f"→ sem decode (PN posição 11 desconhecida)"
                        )
                    continue

            if kp.chip_type == correct_type:
                counts["already_ok"] += 1
                continue

            # ── Precisa corrigir ──────────────────────────────────────────────
            old_type = kp.chip_type
            if verbose:
                self.stdout.write(
                    f"  {kp.fbga_code or '-----'}  {kp.part_number[:48]:<48}  "
                    f"{old_type!r:8} → {correct_type!r}  [{source_tag}]"
                )

            if not dry:
                try:
                    with transaction.atomic():
                        kp.chip_type = correct_type
                        kp.save(update_fields=["chip_type"])
                    if correct_type == "uMCP":
                        counts["ufs_fixed"] += 1
                    else:
                        counts["emmc_fixed"] += 1
                    if source_tag == "url":
                        counts["url_source"] += 1
                    else:
                        counts["pn_source"] += 1
                except Exception as e:
                    logger.warning("Erro ao atualizar %s: %s", kp.part_number, e)
                    counts["errors"] += 1
            else:
                if correct_type == "uMCP":
                    counts["ufs_fixed"] += 1
                else:
                    counts["emmc_fixed"] += 1
                if source_tag == "url":
                    counts["url_source"] += 1
                else:
                    counts["pn_source"] += 1

        # ── Relatório final ───────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Concluído.\n"
            f"   chip_type corrigido → uMCP (UFS):        {counts['ufs_fixed']}\n"
            f"   chip_type corrigido → eMCP (eMMC):       {counts['emmc_fixed']}\n"
            f"     via source_url (produto Micron):        {counts['url_source']}\n"
            f"     via decode do PN (fallback):            {counts['pn_source']}\n"
            f"   já corretos (sem alteração):              {counts['already_ok']}\n"
            f"   sem decode possível:                      {counts['no_decode']}\n"
            f"   Erros:                                    {counts['errors']}\n"
        ))

        if dry:
            self.stdout.write(self.style.WARNING("\nDry run — nenhuma alteração foi salva."))
            return

        # Invalida cache do engine (chip_type mudou)
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            self.stdout.write("   🗑  Cache do engine invalidado.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠  Cache não invalidado: {e}"))
