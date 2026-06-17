"""
refresh_lote
============
Re-classifica AO VIVO cada entrada de um lote e re-grava SÓ o campo
`classification_source` (a coluna "Source" do export), alinhando-o ao catálogo.

Resolve o "rótulo defasado": bless_base / fix_known_parts atualizam o KnownPart
(catálogo), mas NÃO reescrevem o classification_source salvo em cada linha do
InventoryEntry. Este comando faz só isso — NÃO mexe nas specs (capacity, etc.),
para não arriscar regressão.

Só LÊ o catálogo; atualiza apenas classification_source. Dry-run por padrão.
Reversível: --commit grava snapshot; --revert restaura (compatível com snapshots
antigos que guardavam todos os campos).

Uso (DATABASE_URL apontando ao Render):
    python manage.py refresh_lote --lot 39            # dry-run
    python manage.py refresh_lote --lot 39 --commit
    python manage.py refresh_lote --lot 39 --revert
"""

import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chips.engine import classify
from estoque.models import InventoryEntry, Lot

CONFIRMED_CONF = {"confirmed", "manual"}


def _revert_path(n):
    return os.path.join(str(settings.BASE_DIR), f"refresh_lote_{n:03d}_revert.json")


def _live_source(pn):
    """Fonte que o engine atribui AO VIVO. Confirmados SEM família casada caem no
    fallback do classify() (sem classification_source) — deriva "banco de dados"
    da confidence para não APAGAR o rótulo (ex.: códigos Micron JZ###)."""
    r = classify(pn) or {}
    src = r.get("classification_source", "") or ""
    if not src and (r.get("confidence") in CONFIRMED_CONF or r.get("known_exact")):
        src = "banco de dados"
    return src


class Command(BaseCommand):
    help = "Alinha a coluna Source (classification_source) das entradas do lote ao catálogo. Dry-run por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=39)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--revert", action="store_true")

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["lot"])
        try:
            lot = Lot.objects.get(number=opts["lot"])
        except Lot.DoesNotExist:
            raise CommandError(f"Lote #{opts['lot']:03d} não existe.")

        ents = list(InventoryEntry.objects.filter(lot=lot).order_by("part_number"))
        changes = []  # (entry, old, new)
        for e in ents:
            new = _live_source(e.part_number)
            if (e.classification_source or "") != new:
                changes.append((e, e.classification_source, new))

        to_banco = sum(1 for _, _, n in changes if n == "banco de dados")
        mode = self.style.SUCCESS("COMMIT (grava)") if opts["commit"] \
            else self.style.WARNING("DRY-RUN (não grava — use --commit)")
        self.stdout.write("")
        self.stdout.write(f"Lote #{opts['lot']:03d} · {len(ents)} entradas · modo: {mode}")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Source a atualizar: {self.style.SUCCESS(str(len(changes)))}  ·  "
                          f"viram 'banco de dados': {to_banco}")
        for e, a, b in changes[:80]:
            self.stdout.write(f"   {e.part_number:<22} {a or '—'} → {b or '—'}")
        if len(changes) > 80:
            self.stdout.write(f"   ... (+{len(changes) - 80})")

        if not opts["commit"]:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: nada gravado. Rode com --commit."))
            return

        log = {"lot": opts["lot"], "ts": timezone.now().isoformat(), "rows": []}
        with transaction.atomic():
            for e, a, b in changes:
                log["rows"].append({"pk": e.pk, "before": a})  # before = string (só a fonte)
                InventoryEntry.objects.filter(pk=e.pk).update(
                    classification_source=b, last_updated=timezone.now())

        path = _revert_path(opts["lot"])
        if os.path.exists(path):
            os.rename(path, f"{path}.{timezone.now().strftime('%Y%m%d_%H%M%S')}.bak")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\n✅ {len(changes)} Source atualizado(s)."))
        self.stdout.write(f"   Revert: {path}  ·  desfazer: python manage.py refresh_lote --lot {opts['lot']} --revert")

    def _revert(self, n):
        path = _revert_path(n)
        if not os.path.exists(path):
            raise CommandError(f"Revert não encontrado: {path}")
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
        cnt = 0
        with transaction.atomic():
            for row in log.get("rows", []):
                before = row["before"]
                # Compat: snapshots antigos guardavam um dict (todos os campos);
                # os novos guardam só a string da fonte.
                if isinstance(before, dict):
                    cnt += InventoryEntry.objects.filter(pk=row["pk"]).update(**before)
                else:
                    cnt += InventoryEntry.objects.filter(pk=row["pk"]).update(classification_source=before)
        os.rename(path, path + ".done")
        self.stdout.write(self.style.SUCCESS(f"✅ Revertido: {cnt} linha(s). Log → {path}.done"))
