"""
purge_enriched.py
=================
Limpeza pós-remoção do Gemini e do campo status (jun/2026).

⚠ IMPORTANTE — o gate do engine virou "registro com specs reais OU confirmed/manual"
(equivalente fiel ao antigo status="enriched"). Portanto registros `distributor` e
`estimated` QUE TÊM CAPACIDADE continuam sendo usados pelo engine — NÃO são lixo e
NÃO devem ser apagados por padrão. Apagá-los reproduziria a regressão.

Por padrão este comando apaga só o que é comprovadamente inútil:
  • ai_high / ai_medium / ai_low  → resultados antigos de IA (Gemini); E
  • estimated SEM nenhuma capacidade → placeholders vazios da antiga "fila de
    revisão" raw (tinham só chip_type, nenhuma spec).
Também remove as Sources órfãs de IA/Gemini (src_type="ai" ou url "gemini:").

MANTÉM sempre: confirmed, manual, distributor, e estimated COM specs.

Opt-ins explícitos (use com cautela):
  --include-estimated     também apaga estimated COM specs
  --include-distributor   também apaga distributor

Reversível: por padrão grava um JSON de backup das linhas apagadas ANTES de apagar.

Uso:
    python manage.py purge_enriched                       # DRY-RUN (só mostra)
    python manage.py purge_enriched --commit              # apaga ai_* + fila raw vazia
    python manage.py purge_enriched --commit --include-distributor
    python manage.py purge_enriched --commit --no-backup

Regra de ouro #1: ESCREVE no banco → dry-run por padrão; o usuário roda em produção.
Regra de ouro #3: após --commit, REINICIE o servidor (cache do engine).
"""

import json
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count, Q


AI_LEVELS = ["ai_high", "ai_medium", "ai_low"]
# "Sem specs" = nenhuma capacidade preenchida (placeholder vazio da antiga fila raw).
NO_SPECS = Q(capacity="") & Q(emcp_ram="") & Q(emcp_nand="") & Q(density_gbit="")


class Command(BaseCommand):
    help = ("Apaga lixo legado: ai_* (Gemini) e estimated SEM specs (fila raw vazia). "
            "Mantém confirmed/manual/distributor e estimated COM specs. Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit", action="store_true",
            help="Aplica de fato. Sem isto é dry-run (não apaga nada).",
        )
        parser.add_argument(
            "--include-estimated", action="store_true",
            help="Também apaga estimated COM specs (⚠ são usados pelo engine).",
        )
        parser.add_argument(
            "--include-distributor", action="store_true",
            help="Também apaga distributor (⚠ são usados pelo engine).",
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

        # Sempre: lixo de IA + placeholders vazios (estimated sem specs).
        target = Q(confidence__in=AI_LEVELS) | (Q(confidence="estimated") & NO_SPECS)
        if opts["include_estimated"]:
            target |= Q(confidence="estimated")          # nuke estimated COM specs também
        if opts["include_distributor"]:
            target |= Q(confidence="distributor")
        # confirmed/manual nunca entram em target — a base de verdade é intocável.

        qs = KnownPart.objects.filter(target)
        total = qs.count()
        kept = KnownPart.objects.count() - total

        # Breakdown legível: por confidence, separando estimated com/sem specs.
        breakdown = []
        for conf in AI_LEVELS:
            n = qs.filter(confidence=conf).count()
            if n:
                breakdown.append((conf, n))
        est_vazio = qs.filter(confidence="estimated").filter(NO_SPECS).count()
        if est_vazio:
            breakdown.append(("estimated (vazio)", est_vazio))
        est_specs = qs.filter(confidence="estimated").exclude(NO_SPECS).count()
        if est_specs:
            breakdown.append(("estimated (COM specs ⚠)", est_specs))
        dist = qs.filter(confidence="distributor").count()
        if dist:
            breakdown.append(("distributor ⚠", dist))

        ai_sources = (Source.objects.filter(src_type="ai")
                      | Source.objects.filter(url__startswith="gemini:")).distinct()
        ai_src_count = ai_sources.count()

        self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.stdout.write(f"  SERÃO MANTIDOS : {kept}  (confirmed/manual/distributor/estimated-com-specs)")
        self.stdout.write(f"  SERÃO APAGADOS : {total}")
        for label, n in breakdown:
            self.stdout.write(f"    {label:26s} → {n}")
        self.stdout.write(f"  Sources IA/Gemini a remover: {ai_src_count}")
        self.stdout.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if total == 0 and ai_src_count == 0:
            self.stdout.write(self.style.SUCCESS("Nada a apagar."))
            return

        if not opts["commit"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — nada foi apagado. Rode com --commit para aplicar."))
            return

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
