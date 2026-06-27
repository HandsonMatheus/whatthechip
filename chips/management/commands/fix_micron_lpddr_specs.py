"""
fix_micron_lpddr_specs.py — Corrige specs LPDDR Micron (MT5x) congeladas com o bug de dies
============================================================================================
Os FBGA Micron LPDDR (MT53B/MT53D/MT53E, MT52L) criados por enrich_micron_fbga /
fill_capacity_from_micron_api ANTES da correção do parser tiveram as specs CALCULADAS
LOCALMENTE com o bug do D{N} (depth × width × dies ÷ 8). Como são confidence="confirmed",
o valor errado venceu a gramática e ficou congelado no banco: capacity inflado, density_gbit
lixo e, às vezes, subtype/chip_type errados.

A IDENTIDADE (PN ↔ FBGA, vinda da API oficial Micron) está CORRETA e continua "confirmed" —
é o ouro. Só os campos DERIVADOS (calculados em cima do PN) estavam errados. Este comando os
recalcula da fonte certa — o próprio PN, pela fórmula oficial Micron `depth × width ÷ 8`
(atestada contra datasheet/DigiKey/Octopart em 2026-06-27) — e normaliza chip_type/subtype,
SEM tocar em confidence, part_number ou fbga_code.

Campos corrigidos (confirmed/manual Micron MT5x LPDDR):
  • capacity     = depth × width ÷ 8   (fonte única: fix_micron_capacity._decode_lpddr)
  • chip_type    = LPDDR4 / LPDDR4X     (a geração é o tipo, pelo prefixo da família)
  • subtype      = LPDDR4 / LPDDR4X     (canônico)
  • density_gbit = ""  e  density_gb = ""   (LPDDR avulso é triado por capacidade, não por
                                            densidade por die — e o valor estava com o bug de dies)

Determinístico e idempotente: rode quantas vezes quiser, sempre chega no mesmo estado.

Uso:
    python manage.py fix_micron_lpddr_specs --dry-run     # revisa sem salvar
    python manage.py fix_micron_lpddr_specs               # aplica
    python manage.py fix_micron_lpddr_specs --all-confidence  # inclui estimated/distributor
"""

from django.core.management.base import BaseCommand
from django.db import transaction

# Geração por prefixo de família = o chip_type/subtype canônico do LPDDR avulso.
# MT53B/MT53D e MT52L = LPDDR4 (VDDQ 1.1V); MT53E = LPDDR4X (VDDQ 0.6V).
PREFIX_GEN = {
    "MT53E": "LPDDR4X",
    "MT53B": "LPDDR4",
    "MT53D": "LPDDR4",
    "MT52L": "LPDDR4",
}


def _prefix_of(part_number: str):
    pn = (part_number or "").split("-")[0].split(" ")[0].strip().upper()
    for p in PREFIX_GEN:
        if pn.startswith(p):
            return p, pn
    return None, pn


class Command(BaseCommand):
    help = (
        "Corrige specs LPDDR Micron MT5x congeladas com o bug de dies: recalcula capacity "
        "(depth×width÷8), normaliza chip_type/subtype canônicos e limpa density_gbit/density_gb. "
        "Mantém confidence/PN/fbga."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Mostra o que mudaria sem salvar.")
        parser.add_argument("--all-confidence", action="store_true",
                            help="Inclui estimated/distributor (padrão: só confirmed/manual).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart
        from chips.management.commands.fix_micron_capacity import _decode_lpddr

        dry = opts["dry_run"]
        log = self.stdout.write
        if dry:
            log(self.style.WARNING("⚠  DRY RUN — nada será salvo.\n"))

        qs = KnownPart.objects.filter(
            brand__name="Micron", part_number__regex=r"^MT5[23]"
        ).exclude(fbga_code="").exclude(fbga_code__isnull=True)
        if not opts["all_confidence"]:
            qs = qs.filter(confidence__in=["confirmed", "manual"])

        changed = skipped = nodecode = 0
        updates = []
        for kp in qs.order_by("part_number"):
            prefix, pn = _prefix_of(kp.part_number)
            if not prefix:
                continue
            gen = PREFIX_GEN[prefix]
            cap = _decode_lpddr(pn)
            if not cap:
                nodecode += 1
                log(f"  ⚠ sem decode: {kp.part_number}")
                continue

            want = {
                "chip_type":   gen,
                "subtype":     gen,
                "capacity":    cap,
                "density_gbit": "",
                "density_gb":   "",
            }
            diff = {k: v for k, v in want.items() if (getattr(kp, k) or "") != v}
            if not diff:
                skipped += 1
                continue

            changed += 1
            updates.append((kp.pk, want))
            log(f"  {kp.fbga_code:7} {kp.part_number[:26]:26} | "
                + "  ".join(f"{k}: {getattr(kp, k)!r}→{v!r}" for k, v in diff.items()))

        if not dry and updates:
            with transaction.atomic():
                for pk, want in updates:
                    KnownPart.objects.filter(pk=pk).update(**want)

        log(self.style.SUCCESS(
            f"\n{'(dry-run) ' if dry else ''}corrigidos: {changed} | já ok: {skipped} | sem decode: {nodecode}"
        ))
        if not dry and changed:
            try:
                from chips.engine import clear_engine_cache
                clear_engine_cache()
                log("  🗑  Cache do engine invalidado (reinicie o servidor — regra de ouro #3).")
            except Exception as e:
                log(self.style.WARNING(f"  ⚠ cache não invalidado: {e}"))
