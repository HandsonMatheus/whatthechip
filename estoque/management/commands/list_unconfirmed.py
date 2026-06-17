"""
list_unconfirmed
================
Lista (SOMENTE LEITURA) os PNs de um lote com quantidade == --qty que ainda NÃO
são confirmados no banco — checando o KnownPart AO VIVO (não o rótulo gravado no
estoque, que fica defasado do bless_base). Agrupa por marca e grava um CSV.

"Não confirmado" = sem KnownPart confirmed/manual enriched E o engine não devolve
classification_source == "banco de dados".

Uso (DATABASE_URL apontando ao Render):
    python manage.py list_unconfirmed --lot 39 --qty 1
    python manage.py list_unconfirmed --lot 39 --qty 1 --out nao_confirmados_1un.csv
"""

import csv
import os
import re
from collections import OrderedDict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chips.engine import classify
from chips.models import KnownPart
from estoque.models import InventoryEntry, Lot

CONFIRMED_CONF = {"confirmed", "manual"}


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").strip().upper())


def _is_confirmed(pn):
    kp = KnownPart.objects.filter(part_number=_norm(pn)).first()
    if kp and kp.confidence in CONFIRMED_CONF and kp.status == "enriched":
        return True
    r = classify(pn) or {}
    return (r.get("classification_source") == "banco de dados"
            or r.get("confidence") in CONFIRMED_CONF)


class Command(BaseCommand):
    help = "Lista PNs do lote com quantidade == N que ainda NÃO são confirmados (live). Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=39)
        parser.add_argument("--qty", type=int, default=1, help="Quantidade exata (default 1).")
        parser.add_argument("--out", type=str, default="")

    def handle(self, *args, **opts):
        try:
            lot = Lot.objects.get(number=opts["lot"])
        except Lot.DoesNotExist:
            raise CommandError(f"Lote #{opts['lot']:03d} não existe.")

        ents = list(InventoryEntry.objects.filter(lot=lot, quantity=opts["qty"])
                    .order_by("brand", "part_number"))
        nao_conf = [e for e in ents if not _is_confirmed(e.part_number)]

        by_brand = OrderedDict()
        for e in nao_conf:
            by_brand.setdefault(e.brand or "—", []).append(e)

        self.stdout.write("")
        self.stdout.write(f"Lote #{opts['lot']:03d} · qtd == {opts['qty']} · "
                          f"NÃO confirmados: {self.style.WARNING(str(len(nao_conf)))} de {len(ents)}")
        self.stdout.write("=" * 70)
        for brand, items in by_brand.items():
            self.stdout.write(self.style.SUCCESS(f"\n{brand} ({len(items)}):"))
            for e in items:
                self.stdout.write(f"   {e.part_number:<22} {e.chip_type:<8} {e.display_capacity}")

        out = opts["out"] or os.path.join(
            str(settings.BASE_DIR), f"nao_confirmados_lote{opts['lot']:03d}_q{opts['qty']}.csv")
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["marca", "part_number", "tipo", "capacidade"])
            for brand, items in by_brand.items():
                for e in items:
                    w.writerow([brand, e.part_number, e.chip_type, e.display_capacity])
        self.stdout.write(f"\nCSV (por marca): {out}")
