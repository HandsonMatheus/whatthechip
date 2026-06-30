"""
resnapshot_lote.py
==================
Passo 2 (atualização do estoque): re-roda o snapshot do servidor
(`_snapshot(classify(pn))`) para as entradas DEFASADAS de um lote — aquelas cujo
`snapshot_catalog_version` é menor que `CatalogVersion.current()` (o catálogo
melhorou desde que o chip foi lançado, ex.: o fix Micron 48GB→6GB). Reescreve os
campos do snapshot (chip_type/capacity/emcp_*/interface/Source), atualiza o
carimbo de versão e a **data de última atualização**.

É o caminho PRINCIPAL de revaluação (a tela do estoque faz o mesmo on-read, mas só
das linhas visíveis). Diferente do `refresh_lote`, que só reescreve a coluna Source.

Dry-run por padrão. `--commit` grava (revert em `var/reverts/`). `--revert` desfaz.

Uso:
    python manage.py resnapshot_lote --lot 39            # dry-run
    python manage.py resnapshot_lote --lot 39 --commit
    python manage.py resnapshot_lote --all --commit      # todos os lotes
    python manage.py resnapshot_lote --revert
"""

import json
import os

from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand

_REVERT_DIR = "var/reverts"
_REVERT = os.path.join(_REVERT_DIR, "resnapshot_lote_revert.json")

# Campos que o resnapshot reescreve (espelho do _snapshot, sem confidence, + carimbo + data).
_FIELDS = [
    "chip_type", "brand", "capacity", "emcp_ram", "emcp_nand", "is_emcp",
    "interface", "classification_source", "snapshot_catalog_version", "last_updated",
]
# Campos vindos de _snapshot (sem confidence) — usados para detectar mudança.
_SNAP_KEYS = [
    "chip_type", "brand", "capacity", "emcp_ram", "emcp_nand", "is_emcp",
    "interface", "classification_source",
]
CONFIRMED_CONF = {"confirmed", "manual"}


class Command(SafeWriteCommand):
    help = ("Re-snapshota as entradas DEFASADAS de um lote (catálogo melhorou). "
            "Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, help="Número do lote.")
        parser.add_argument("--all", action="store_true", help="Todos os lotes.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Não grava — é o padrão (sem --commit). Aceito p/ ser explícito.")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--revert", action="store_true")

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert()

        from chips.engine import classify
        from chips.models import CatalogVersion
        from estoque.models import InventoryEntry, Lot
        from estoque.views import _snapshot

        cur = CatalogVersion.current()
        qs = InventoryEntry.objects.all()
        if not opts["all"]:
            if not opts["lot"]:
                raise CommandError("Use --lot N ou --all.")
            lot = Lot.objects.filter(number=opts["lot"]).first()
            if not lot:
                raise CommandError(f"Lote #{opts['lot']} não existe.")
            qs = qs.filter(lot=lot)

        stale = list(qs.filter(snapshot_catalog_version__lt=cur).order_by("part_number"))
        self.stdout.write(
            f"\nEdição atual do catálogo: {cur}  ·  entradas defasadas: {len(stale)}")

        changed = []  # (entry, before_dict)
        for e in stale:
            r = classify(e.part_number) or {}
            snap = _snapshot(r)
            snap.pop("confidence", None)
            # Não apagar o rótulo de confirmados SEM família casada (ex.: Micron JZ###):
            # deriva 'banco de dados' da confiança, igual ao refresh_lote._live_source.
            if not snap["classification_source"] and (
                    r.get("confidence") in CONFIRMED_CONF or r.get("known_exact")):
                snap["classification_source"] = "banco de dados"
            before = {k: getattr(e, k) for k in _SNAP_KEYS}
            before["snapshot_catalog_version"] = e.snapshot_catalog_version  # p/ o revert
            specs_mudaram = any(before[k] != snap[k] for k in _SNAP_KEYS)
            # aplica (specs + carimbo) — a entrada sai da defasagem mesmo se as specs
            # não mudaram (ex.: só a rentabilidade mudou): o carimbo precisa avançar.
            for k in _SNAP_KEYS:
                setattr(e, k, snap[k])
            e.snapshot_catalog_version = cur
            changed.append((e, before))
            if specs_mudaram:
                diffs = ", ".join(f"{k}: {before[k]!r}→{snap[k]!r}"
                                  for k in _SNAP_KEYS if before[k] != snap[k])
                self.stdout.write(f"  {e.part_number:<24} {diffs}")

        if not changed:
            self.stdout.write(self.style.SUCCESS("Nada defasado — tudo na edição atual."))
            return
        if opts["dry_run"] or not opts["commit"]:
            self.stdout.write(self.style.WARNING(
                f"\nDRY-RUN: {len(changed)} entrada(s) seriam atualizadas. --commit para gravar."))
            return

        now = timezone.now()
        log = {"version": cur, "rows": []}
        with transaction.atomic():
            for e, before in changed:
                log["rows"].append({"pk": e.pk, "before": before})
                e.last_updated = now
            InventoryEntry.objects.bulk_update([e for e, _ in changed], _FIELDS, batch_size=500)

        os.makedirs(_REVERT_DIR, exist_ok=True)
        with open(_REVERT, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1, default=str)
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {len(changed)} atualizada(s).  Revert: {_REVERT}  ·  "
            f"desfazer: python manage.py resnapshot_lote --revert"))

    def _revert(self):
        from estoque.models import InventoryEntry
        if not os.path.exists(_REVERT):
            raise CommandError(f"Revert não encontrado: {_REVERT}")
        with open(_REVERT, encoding="utf-8") as fh:
            log = json.load(fh)
        n = 0
        with transaction.atomic():
            for row in log["rows"]:
                n += InventoryEntry.objects.filter(pk=row["pk"]).update(**row["before"])
        os.rename(_REVERT, _REVERT + ".done")
        self.stdout.write(self.style.SUCCESS(f"✅ Revertido: {n} linha(s). Log → {_REVERT}.done"))
