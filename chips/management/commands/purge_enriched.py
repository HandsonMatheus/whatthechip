"""
purge_enriched.py
=================
Limpeza pós-remoção do Gemini e do campo status (jun/2026).

Quando o gate do engine passou a ser confidence ∈ (confirmed, manual), os
registros KnownPart abaixo ficaram INVISÍVEIS ao engine e viraram apenas ruído
no banco. Este comando os apaga:

  • ai_high / ai_medium / ai_low  → resultados antigos de IA (Gemini);
  • estimated                     → estimativas e a antiga "fila de revisão" raw
                                    (era criada a cada busca de PN não confirmado,
                                    sempre com confidence=estimated).

Mantém SEMPRE confirmed e manual (a base de verdade). distributor é mantido por
padrão (use --include-distributor para apagá-lo também). Também remove as Sources
órfãs de IA/Gemini (src_type="ai" ou url começando com "gemini:").

Reversível: por padrão grava um JSON de backup das linhas apagadas ANTES de apagar.

Uso:
    python manage.py purge_enriched                       # DRY-RUN (só mostra)
    python manage.py purge_enriched --commit              # apaga (grava backup antes)
    python manage.py purge_enriched --commit --include-distributor
    python manage.py purge_enriched --commit --keep estimated   # poupa 'estimated'
    python manage.py purge_enriched --commit --no-backup

Regra de ouro #1: ESCREVE no banco → dry-run por padrão; o usuário roda em produção.
Regra de ouro #3: após --commit, REINICIE o servidor (cache do engine).
"""

import json
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count


# Níveis legados que deixaram de ser visíveis ao engine (gate = confirmed/manual).
LEGACY_CONFIDENCE = ["ai_high", "ai_medium", "ai_low", "estimated"]


class Command(BaseCommand):
    help = ("Apaga KnownParts legados de IA/estimados (invisíveis ao engine após a "
            "remoção do status) e Sources órfãs de Gemini. Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit", action="store_true",
            help="Aplica de fato. Sem isto é dry-run (não apaga nada).",
        )
        parser.add_argument(
            "--include-distributor", action="store_true",
            help="Também apaga confidence='distributor' (por padrão é mantido).",
        )
        parser.add_argument(
            "--keep", nargs="*", default=[], metavar="CONFIDENCE",
            help="Níveis de confidence a preservar além de confirmed/manual.",
        )
        parser.add_argument(
            "--backup", default="", metavar="PATH",
            help="Caminho do JSON de backup (default: purge_enriched_backup_<ts>.json).",
        )
        parser.add_argument(
            "--no-backup", action="store_true",
            help="Não grava o JSON de backup antes de apagar.",
        )

    def handle(self, *args, **opts):
        from chips.models import KnownPart, Source

        # Monta o conjunto-alvo. confirmed/manual NUNCA entram (base de verdade).
        targets = set(LEGACY_CONFIDENCE)
        if opts["include_distributor"]:
            targets.add("distributor")
        targets -= set(opts["keep"])
        targets -= {"confirmed", "manual"}

        qs = KnownPart.objects.filter(confidence__in=targets)
        total = qs.count()
        kept = KnownPart.objects.exclude(confidence__in=targets).count()
        breakdown = qs.values("confidence").annotate(n=Count("id")).order_by("-n")

        # Sources órfãs de IA/Gemini (a "Gemini Live Search" e quaisquer src_type="ai").
        ai_sources = Source.objects.filter(src_type="ai") | Source.objects.filter(
            url__startswith="gemini:"
        )
        ai_sources = ai_sources.distinct()
        ai_src_count = ai_sources.count()

        self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.stdout.write(f"  Alvos (apagar)  : {sorted(targets)}")
        self.stdout.write(f"  SERÃO MANTIDOS  : {kept}")
        self.stdout.write(f"  SERÃO APAGADOS  : {total}")
        for row in breakdown:
            self.stdout.write(f"    {row['confidence']:14s} → {row['n']}")
        self.stdout.write(f"  Sources IA/Gemini a remover: {ai_src_count}")
        self.stdout.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if total == 0 and ai_src_count == 0:
            self.stdout.write(self.style.SUCCESS("Nada a apagar."))
            return

        if not opts["commit"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — nada foi apagado. Rode com --commit para aplicar."))
            return

        # Backup antes de apagar (reversibilidade)
        if not opts["no_backup"] and total:
            path = opts["backup"] or f"purge_enriched_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
            rows = list(qs.values(
                "part_number", "confidence", "chip_type", "subtype", "capacity",
                "density_gbit", "density_gb", "emcp_ram", "emcp_nand", "interface",
                "fbga_code", "device", "notes", "source_url",
            ))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"ts": datetime.now().isoformat(), "deleted": rows},
                          fh, ensure_ascii=False, indent=2)
            self.stdout.write(f"Backup gravado: {path} ({len(rows)} linha(s))")

        deleted, _ = qs.delete()
        src_deleted, _ = ai_sources.delete()
        self.stdout.write(self.style.SUCCESS(
            f"✅ {deleted} KnownPart(s) e {src_deleted} Source(s) IA/Gemini apagado(s)."))
        self.stdout.write(self.style.WARNING(
            "⚠ REINICIE o servidor para o engine recarregar (regra de ouro #3)."))
