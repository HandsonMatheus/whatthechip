"""
reconcile_lote_039
==================
Iguala o estoque do SISTEMA ao estoque FÍSICO recontado do lote #039 —
SEM criar part numbers inventados.

Em cada categoria da planilha (ver estoque/reconcile_core.RECOUNT_039) o comando:
  1. Soma quanto o lote JÁ tem de chips REAIS (agrupando pelas mesmas categorias
     da planilha; ver category_key). Entradas da tentativa antiga (marca
     classification_source="recount_039") são ignoradas e removidas no --commit.
  2. delta = (físico recontado) − (sistema atual real).
  3. delta > 0  -> escolhe o chip REAL de MAIOR quantidade naquela categoria
     (o "mais comum" já lançado pelo operador) e SOMA o delta na quantidade dele.
     Nenhum PN novo é criado.
  4. delta == 0 -> nada. delta < 0 (sistema > físico) -> só avisa, não remove.

Categorias que existem no sistema mas não na planilha (uMCP, UFS 32/128GB, etc.)
não são tocadas — só reportadas.

Regra de ouro #1: este comando ESCREVE no banco -> roda em --dry-run por padrão.

Uso:
    python manage.py reconcile_lote_039            # dry-run (não grava)
    python manage.py reconcile_lote_039 --commit   # aplica
    python manage.py reconcile_lote_039 --revert    # desfaz o último --commit

Reversível: o --commit grava um log (reconcile_039_revert.json em BASE_DIR) com
exatamente o que foi somado; --revert subtrai de volta.
"""

import json
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from estoque.models import InventoryEntry, Lot
from estoque.reconcile_core import (
    LOTE,
    RECOUNT_SOURCE,
    category_key,
    compute_reconciliation,
    self_check,
)

REVERT_LOG = os.path.join(str(settings.BASE_DIR), "reconcile_039_revert.json")


class Command(BaseCommand):
    help = "Reconcilia o lote #039 somando a diferença em chips reais já existentes (sem PN inventado)."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=LOTE)
        parser.add_argument("--commit", action="store_true",
                            help="Aplica as somas. Sem isso, só simula (dry-run).")
        parser.add_argument("--revert", action="store_true",
                            help="Desfaz o último --commit (lê reconcile_039_revert.json).")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _entry_key(self, e):
        return category_key(
            chip_type=e.chip_type, capacity=e.capacity,
            emcp_nand=e.emcp_nand, emcp_ram=e.emcp_ram,
            is_emcp=e.is_emcp, interface=e.interface,
        )

    def _get_lot(self, lot_number):
        try:
            return Lot.objects.get(number=lot_number)
        except Lot.DoesNotExist:
            raise CommandError(f"Lote #{lot_number:03d} não existe.")

    # ── main ──────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["lot"])

        problems = self_check()
        if problems:
            raise CommandError("RECOUNT_039 inconsistente:\n  - " + "\n  - ".join(problems))

        lot = self._get_lot(opts["lot"])
        commit = opts["commit"]
        lot_number = opts["lot"]

        # Separa resíduo da tentativa antiga (entradas filler) dos chips reais.
        placeholders = list(lot.entries.filter(classification_source=RECOUNT_SOURCE))
        real_entries = [e for e in lot.entries.all()
                        if e.classification_source != RECOUNT_SOURCE]

        # Estado atual (só chips reais), agrupado por categoria.
        existing_counts = {}
        entries_by_cat = {}
        uncategorized = []
        for e in real_entries:
            k = self._entry_key(e)
            if k is None:
                uncategorized.append(e)
                continue
            existing_counts[k] = existing_counts.get(k, 0) + e.quantity
            entries_by_cat.setdefault(k, []).append(e)

        plan = compute_reconciliation(existing_counts)
        rows, extras, totals = plan["rows"], plan["extras"], plan["totals"]

        # Para cada categoria a completar, decide QUAL chip real recebe o delta.
        actions = []          # (row, chosen_entry)  ou (row, None) se não houver chip real
        missing_real = []
        for r in rows:
            if r["action"] != "add":
                continue
            cands = entries_by_cat.get(r["key"], [])
            if not cands:
                missing_real.append(r)
                continue
            # chip "mais comum": maior quantidade; desempate pelo maior pk.
            chosen = max(cands, key=lambda e: (e.quantity, e.pk))
            actions.append((r, chosen))

        # ── relatório ─────────────────────────────────────────────────────────
        mode = self.style.SUCCESS("COMMIT (grava)") if commit \
            else self.style.WARNING("DRY-RUN (não grava — use --commit)")
        ph_chips = sum(e.quantity for e in placeholders)
        self.stdout.write("")
        self.stdout.write(f"Lote #{lot_number:03d}  ·  operador: {lot.operator}  ·  modo: {mode}")
        if placeholders:
            self.stdout.write(self.style.WARNING(
                f"Resíduo da tentativa antiga: {len(placeholders)} entrada(s) "
                f"placeholder ({ph_chips} chips) — serão REMOVIDAS no --commit."))
        self.stdout.write("=" * 86)
        self.stdout.write(f"{'CATEGORIA':<16}{'FÍSICO':>7}{'SISTEMA':>8}{'+ADD':>6}   CHIP REAL QUE RECEBE A SOMA")
        self.stdout.write("-" * 86)

        chosen_map = {id(r): ch for r, ch in actions}
        for r in rows:
            if r["action"] == "ok":
                self.stdout.write(f"{r['key']:<16}{r['target']:>7}{r['current']:>8}{'—':>6}   (já bate)")
            elif r["action"] == "over":
                self.stdout.write(
                    f"{r['key']:<16}{r['target']:>7}{r['current']:>8}"
                    + self.style.ERROR(f"{r['delta']:>6}") + "   (sistema > físico — não mexo)")
            else:  # add
                ch = chosen_map.get(id(r))
                if ch is None:
                    info = self.style.ERROR("⚠ nenhum chip real nessa categoria — ver aviso abaixo")
                else:
                    info = f"{ch.part_number}  ({ch.quantity} → {ch.quantity + r['delta']})"
                self.stdout.write(
                    f"{r['key']:<16}{r['target']:>7}{r['current']:>8}"
                    + self.style.SUCCESS(f"+{r['delta']:<5}") + f"  {info}")

        self.stdout.write("-" * 86)
        self.stdout.write(
            f"Físico: {totals['recount_total']}   "
            f"Sistema real (nas categorias): {totals['current_in_recount']}   "
            f"A SOMAR: {self.style.SUCCESS(str(totals['to_add']))}")

        if extras:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "⚠ Categorias no sistema fora da planilha (NÃO tocadas):"))
            for k, v in sorted(extras.items()):
                self.stdout.write(f"    {k:<18} {v}")
        if missing_real:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(
                "⚠ Categorias que precisam de chips mas NÃO têm nenhum chip real no lote "
                "(não dá pra somar sem inventar PN — lance 1 unidade manualmente e rode de novo):"))
            for r in missing_real:
                self.stdout.write(f"    {r['key']:<16} faltam {r['delta']}")
        if uncategorized:
            self.stdout.write(self.style.WARNING(
                f"⚠ {len(uncategorized)} entrada(s) real(is) sem categoria reconhecível — ignoradas."))

        if not commit:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: nada gravado. Revise os chips que receberão a soma e rode com --commit."))
            return

        # ── commit (atômico) ───────────────────────────────────────────────────
        log = {"lot": lot_number, "ts": datetime.now().isoformat(),
               "removed_placeholders": len(placeholders), "bumps": []}
        with transaction.atomic():
            for e in placeholders:
                e.delete()
            for r, ch in actions:
                # relê e trava a linha para somar com segurança
                obj = InventoryEntry.objects.select_for_update().get(pk=ch.pk)
                before = obj.quantity
                obj.quantity = before + r["delta"]
                obj.last_updated = timezone.now()
                obj.save(update_fields=["quantity", "last_updated"])
                log["bumps"].append({"pk": obj.pk, "pn": obj.part_number,
                                     "delta": r["delta"], "before": before,
                                     "after": obj.quantity})

        if log["bumps"]:
            with open(REVERT_LOG, "w", encoding="utf-8") as fh:
                json.dump(log, fh, ensure_ascii=False, indent=2)

        new_total = sum(e.quantity for e in lot.entries.all())
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ {len(log['bumps'])} chip(s) tiveram a quantidade somada (+{totals['to_add']} no total). "
            f"{len(placeholders)} placeholder(s) removido(s)."))
        self.stdout.write(f"   Lote #{lot_number:03d} agora soma {new_total} chips no sistema.")
        if log["bumps"]:
            self.stdout.write(f"   Log de reversão: {REVERT_LOG}")
            self.stdout.write("   Desfazer: python manage.py reconcile_lote_039 --revert")

    # ── revert ──────────────────────────────────────────────────────────────────

    def _revert(self, lot_number):
        if not os.path.exists(REVERT_LOG):
            raise CommandError(f"Log de reversão não encontrado em {REVERT_LOG}. Nada a desfazer.")
        with open(REVERT_LOG, encoding="utf-8") as fh:
            log = json.load(fh)

        restored = 0
        with transaction.atomic():
            for b in log.get("bumps", []):
                obj = InventoryEntry.objects.select_for_update().filter(pk=b["pk"]).first()
                if not obj:
                    self.stdout.write(self.style.WARNING(
                        f"  entrada pk={b['pk']} ({b['pn']}) não existe mais — pulada."))
                    continue
                new_q = max(0, obj.quantity - b["delta"])
                obj.quantity = new_q
                obj.last_updated = timezone.now()
                obj.save(update_fields=["quantity", "last_updated"])
                restored += 1

        os.rename(REVERT_LOG, REVERT_LOG + ".done")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Revertido: {restored} chip(s) voltaram à quantidade anterior. "
            f"Log arquivado em {REVERT_LOG}.done"))
        self.stdout.write(self.style.WARNING(
            "Obs.: os placeholders removidos no commit NÃO voltam (eram lixo). "
            "O lote volta ao estado real de antes da soma."))
