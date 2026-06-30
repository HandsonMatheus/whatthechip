"""
restore_purge.py
================
Restaura KnownParts apagados por um `purge_enriched` anterior, a partir do JSON de
backup que ele grava. Serve para desfazer uma limpeza ampla demais.

Por padrão restaura SÓ o que vale a pena — registros com **specs reais**
(capacity/emcp_ram/emcp_nand/density). PULA os placeholders vazios da antiga "fila
de revisão" (notes "Fila de revisão", sem capacidade) e os `ai_*` (lixo de IA/
Gemini), que eram exatamente o que o purge devia remover. Use --all p/ restaurar tudo.

• Nunca sobrescreve um KnownPart já existente (não rebaixa confirmed/manual).
• Marca/família são re-derivadas pelo prefixo do PN (_match_family); registros sem
  família casável são pulados e listados (atribua a marca à mão depois).

Uso (DATABASE_URL apontando ao banco a recuperar):
    python manage.py restore_purge                       # DRY-RUN, backup mais recente
    python manage.py restore_purge --commit
    python manage.py restore_purge --file purge_enriched_backup_20260626_130657.json --commit
    python manage.py restore_purge --all --commit        # também vazios/ai_* (raramente útil)
Após --commit, REINICIE o servidor (cache do engine).
"""

import glob
import json
import re

from django.core.management.base import CommandError

from core.safe_command import SafeWriteCommand


AI = {"ai_high", "ai_medium", "ai_low"}
FIELDS = ["chip_type", "subtype", "capacity", "density_gbit", "density_gb",
          "emcp_ram", "emcp_nand", "interface", "fbga_code", "device",
          "notes", "source_url"]


def _has_specs(r):
    return bool(r.get("capacity") or r.get("emcp_ram") or r.get("emcp_nand") or r.get("density_gbit"))


class Command(SafeWriteCommand):
    help = "Restaura KnownParts de um backup do purge_enriched. Dry-run por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="", help="JSON de backup (default: o mais recente no diretório).")
        parser.add_argument("--all", action="store_true", help="Restaura tudo (inclui vazios e ai_*).")
        parser.add_argument("--commit", action="store_true", help="Aplica de fato (sem isto é dry-run).")

    def handle(self, *args, **opts):
        from chips.models import KnownPart
        from chips.engine import _match_family

        path = opts["file"]
        if not path:
            cands = sorted(glob.glob("purge_enriched_backup_*.json"))
            if not cands:
                raise CommandError("Nenhum purge_enriched_backup_*.json encontrado. Use --file.")
            path = cands[-1]

        data = json.load(open(path, encoding="utf-8"))
        rows = data.get("deleted", [])
        self.stdout.write(f"Backup: {path}  (ts={data.get('ts')}, {len(rows)} linhas)")

        if opts["all"]:
            target = rows
        else:
            target = [r for r in rows if _has_specs(r) and r.get("confidence") not in AI]
        pulados_filtro = len(rows) - len(target)

        to_create, skipped, no_brand = [], 0, 0
        for r in target:
            pn = r.get("part_number") or ""
            if not pn or KnownPart.objects.filter(part_number=pn).exists():
                skipped += 1
                continue
            fam = _match_family(re.sub(r"[^A-Z0-9]", "", pn.upper()))
            if not (fam and fam.brand_id):
                no_brand += 1
                continue
            to_create.append((r, fam))

        self.stdout.write("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if not opts["all"]:
            self.stdout.write(f"  Pulados por filtro (vazios/ai_*): {pulados_filtro}")
        self.stdout.write(f"  Já existem no banco (pulados)   : {skipped}")
        self.stdout.write(f"  Sem família casável (pulados)   : {no_brand}")
        self.stdout.write(f"  A RESTAURAR                     : {len(to_create)}")
        self.stdout.write("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        if not opts["commit"]:
            for r, fam in to_create[:20]:
                self.stdout.write(f"    + {r['part_number']:22s} {(r.get('confidence') or ''):11s} {fam.brand.name}")
            if len(to_create) > 20:
                self.stdout.write(f"    ... (+{len(to_create) - 20})")
            self.stdout.write(self.style.WARNING("\nDRY-RUN — nada gravado. Rode com --commit."))
            return

        created = 0
        for r, fam in to_create:
            KnownPart.objects.create(
                part_number=r["part_number"], brand=fam.brand, family=fam,
                confidence=r.get("confidence") or "estimated",
                **{f: (r.get(f) or "") for f in FIELDS},
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"✅ {created} KnownPart(s) restaurado(s) de {path}."))
        if no_brand:
            self.stdout.write(self.style.WARNING(
                f"⚠ {no_brand} registro(s) sem família casável NÃO foram restaurados "
                f"(rode com --file e veja o backup para tratá-los à mão)."))
        self.stdout.write(self.style.WARNING("⚠ REINICIE o servidor (cache do engine, regra de ouro #3)."))
