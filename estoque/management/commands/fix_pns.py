"""
fix_pns
=======
Corrige PNs no estoque a partir de um CSV de mapeamento `errado,certo`. Como os
chips FÍSICOS já entraram no estoque, NÃO se deleta — corrige-se a entrada:

  - errado == certo   -> REFRESH: reclassifica e atualiza specs + fonte da própria
                         entrada (ex.: PN certo que só estava como "gramática" e
                         agora virou confirmado, ou specs corrigidas no engine).
  - certo já existe    -> MERGE: soma a quantidade do errado na entrada certa
                         (preservando a contagem física) e remove a entrada errada.
  - certo não existe   -> RENAME: renomeia a entrada errada para o PN certo e
                         atualiza as specs.

As specs vêm de `classify(certo)` — então rode DEPOIS de ter o PN certo confirmado
no banco (add_confirmed_part / populate_*) para a fonte virar "banco de dados".
Avisa quando o destino ainda não é confirmado.

Regra de ouro #1: ESCREVE no banco -> dry-run por padrão.
Reversível: --commit grava fix_pns_<lot>_revert.json; --revert desfaz.

CSV (uma correção por linha; cabeçalho opcional; vírgula):
    errado,certo
    H26T87001CMB,H26T87001CMR
    H26M78103CCR,H26M78103CCR     # refresh no lugar
    H9HP16AECMMD,H9HP16AECMMD

Uso (DATABASE_URL apontando ao Render — ver DEPLOY_RENDER.md):
    python manage.py fix_pns --lot 39 --file correcoes_sk_hynix.csv           # dry-run
    python manage.py fix_pns --lot 39 --file correcoes_sk_hynix.csv --commit  # aplica
    python manage.py fix_pns --lot 39 --revert                                # desfaz
"""

import csv
import json
import os
import re

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand
from django.db.models import F
from django.utils import timezone

from chips.engine import classify
from estoque.models import InventoryEntry, Lot

CONFIRMED_SOURCES = {"banco de dados"}
CONFIRMED_CONF = {"confirmed", "manual"}


def _norm(raw):
    return re.sub(r"[^A-Z0-9\-]", "", (raw or "").strip().upper())


def _revert_path(lot_number):
    return os.path.join(str(settings.BASE_DIR), f"fix_pns_{lot_number:03d}_revert.json")


def _specs_from_classify(pn):
    """Roda o engine e devolve os campos de InventoryEntry + se é confirmado."""
    r = classify(pn) or {}
    confirmed = (r.get("classification_source") in CONFIRMED_SOURCES
                 or r.get("confidence") in CONFIRMED_CONF)
    fields = dict(
        chip_type=r.get("chip_type", "") or "",
        brand=r.get("brand", "") or "",
        capacity=r.get("capacity", "") or "",
        emcp_ram=r.get("emcp_ram", "") or "",
        emcp_nand=r.get("emcp_nand", "") or "",
        is_emcp=bool(r.get("is_emcp")),
        interface=r.get("interface", "") or "",
        classification_source=r.get("classification_source", "") or "",
    )
    return fields, confirmed


def _snapshot(e):
    return dict(
        pk=e.pk, part_number=e.part_number, quantity=e.quantity,
        chip_type=e.chip_type, brand=e.brand, capacity=e.capacity,
        emcp_ram=e.emcp_ram, emcp_nand=e.emcp_nand, is_emcp=e.is_emcp,
        interface=e.interface, classification_source=e.classification_source,
        added_at=e.added_at.isoformat(), last_updated=e.last_updated.isoformat(),
    )


class Command(SafeWriteCommand):
    help = "Corrige PNs do estoque (merge/rename/refresh) a partir de um CSV errado,certo. Dry-run por padrão."

    def add_arguments(self, parser):
        # T3 (multi-empresa): comando tenant-scoped roda com escopo explícito.
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório com 2+ empresas ativas).')
        parser.add_argument("--lot", type=int, default=39)
        parser.add_argument("--file", type=str, help="CSV com linhas 'errado,certo'.")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--revert", action="store_true")

    def _get_lot(self, n):
        try:
            return Lot.objects.get(number=n)
        except Lot.DoesNotExist:
            raise CommandError(f"Lote #{n:03d} não existe.")

    def _read_csv(self, path):
        if not path or not os.path.exists(path):
            raise CommandError(f"CSV não encontrado: {path}")
        pairs = []
        with open(path, encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if not row or not row[0].strip():
                    continue
                wrong = _norm(row[0])
                correct = _norm(row[1]) if len(row) > 1 and row[1].strip() else wrong
                if wrong.lower() in ("errado", "wrong", "pn"):  # cabeçalho
                    continue
                pairs.append((wrong, correct))
        return pairs

    def handle(self, *args, **opts):
        # T3: seta o escopo fail-closed do processo ANTES de qualquer query
        # (os managers do estoque explodem sem empresa — de propósito).
        from tenancy.scope import scope_command_to_company
        scope_command_to_company(opts.get('company'), stdout=self.stdout)
        if opts["revert"]:
            return self._revert(opts["lot"])

        lot = self._get_lot(opts["lot"])
        commit = opts["commit"]
        pairs = self._read_csv(opts["file"])

        plan = []      # (action, wrong, correct, src, dst, fields, confirmed)
        for wrong, correct in pairs:
            src = InventoryEntry.objects.filter(lot=lot, part_number=wrong).first()
            if not src:
                plan.append(("nao_encontrado", wrong, correct, None, None, None, None))
                continue
            fields, confirmed = _specs_from_classify(correct)
            if wrong == correct:
                plan.append(("refresh", wrong, correct, src, None, fields, confirmed))
            else:
                dst = InventoryEntry.objects.filter(lot=lot, part_number=correct).first()
                action = "merge" if dst else "rename"
                plan.append((action, wrong, correct, src, dst, fields, confirmed))

        # ── relatório ─────────────────────────────────────────────────────────
        mode = self.style.SUCCESS("COMMIT (grava)") if commit \
            else self.style.WARNING("DRY-RUN (não grava — use --commit)")
        self.stdout.write("")
        self.stdout.write(f"Lote #{opts['lot']:03d} · correções: {len(pairs)} · modo: {mode}")
        self.stdout.write("=" * 92)
        warns = 0
        # Estado projetado p/ o preview: quantidade por PN e quais PNs existem.
        # Reproduz a sequência — um alvo recém-criado por um rename vira MERGE no
        # passo seguinte que apontar pra ele (ex.: dois typos → mesmo alvo novo).
        qty_by_pn, exists = {}, set()
        for e in InventoryEntry.objects.filter(lot=lot):
            qty_by_pn[e.part_number] = e.quantity
            exists.add(e.part_number)
        for action, wrong, correct, src, dst, fields, confirmed in plan:
            if action == "nao_encontrado":
                self.stdout.write(self.style.ERROR(f"  ✗ {wrong:<18} não está no lote — pulado"))
                continue
            flag = "" if confirmed else self.style.WARNING("  ⚠ destino ainda NÃO confirmado")
            sq = src.quantity if src else 0
            if wrong == correct:
                self.stdout.write(f"  ↻ REFRESH {wrong:<18} specs/fonte → {fields['classification_source'] or '—'}{flag}")
            elif correct in exists:
                base = qty_by_pn.get(correct, 0)
                after = base + sq
                qty_by_pn[correct] = after
                exists.discard(wrong); qty_by_pn.pop(wrong, None)
                self.stdout.write(
                    f"  ⇶ MERGE   {wrong:<18} (×{sq}) → {correct} "
                    f"({base} → {after}); remove o errado{flag}")
            else:
                qty_by_pn[correct] = sq
                exists.add(correct); exists.discard(wrong); qty_by_pn.pop(wrong, None)
                self.stdout.write(f"  ✎ RENAME  {wrong:<18} → {correct} (atualiza specs){flag}")
            if not confirmed:
                warns += 1
        self.stdout.write("-" * 92)
        if warns:
            self.stdout.write(self.style.WARNING(
                f"{warns} destino(s) ainda não confirmado(s) no banco. Rode add_confirmed_part/"
                "populate_* contra o mesmo banco ANTES de aplicar, para a fonte virar 'banco de dados'."))

        if not commit:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: nada gravado. Revise e rode com --commit."))
            return

        # ── commit ────────────────────────────────────────────────────────────
        log = {"lot": opts["lot"], "ts": timezone.now().isoformat(), "ops": []}
        with transaction.atomic():
            for action, wrong, correct, src0, dst0, fields, confirmed in plan:
                if action == "nao_encontrado":
                    continue
                # Reavalia o estado AGORA (operações anteriores deste mesmo run podem
                # ter criado/alterado o destino). Assim, dois typos no mesmo alvo que
                # ainda não existia: o 1º vira rename (cria), o 2º vira merge.
                src = InventoryEntry.objects.select_for_update().filter(
                    lot=lot, part_number=wrong).first()
                if not src:
                    continue
                if wrong == correct:
                    log["ops"].append({"action": "refresh", "before": _snapshot(src)})
                    for k, v in fields.items():
                        setattr(src, k, v)
                    src.save()
                    continue
                dst = InventoryEntry.objects.select_for_update().filter(
                    lot=lot, part_number=correct).first()
                if dst and dst.pk != src.pk:
                    # MERGE — F() acumula no valor atual; múltiplos typos somam certo.
                    log["ops"].append({"action": "merge",
                                       "wrong_snapshot": _snapshot(src),
                                       "dst_before": _snapshot(dst)})
                    InventoryEntry.objects.filter(pk=dst.pk).update(
                        quantity=F("quantity") + src.quantity,
                        last_updated=timezone.now(), **fields)
                    src.delete()
                else:
                    # RENAME
                    log["ops"].append({"action": "rename", "before": _snapshot(src)})
                    src.part_number = correct
                    for k, v in fields.items():
                        setattr(src, k, v)
                    src.last_updated = timezone.now()
                    src.save()

        path = _revert_path(opts["lot"])
        # Não clobberar um revert anterior (ex.: lote SK já aplicado): arquiva antes.
        if os.path.exists(path):
            os.rename(path, f"{path}.{timezone.now().strftime('%Y%m%d_%H%M%S')}.bak")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\n✅ {len(log['ops'])} correção(ões) aplicada(s)."))
        self.stdout.write(f"   Revert: {path}  ·  desfazer: python manage.py fix_pns --lot {opts['lot']} --revert")

    # ── revert ──────────────────────────────────────────────────────────────────

    def _revert(self, lot_number):
        path = _revert_path(lot_number)
        if not os.path.exists(path):
            raise CommandError(f"Revert não encontrado: {path}")
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
        lot = self._get_lot(lot_number)

        def restore_fields(pk, snap):
            InventoryEntry.objects.filter(pk=pk).update(
                part_number=snap["part_number"], quantity=snap["quantity"],
                chip_type=snap["chip_type"], brand=snap["brand"], capacity=snap["capacity"],
                emcp_ram=snap["emcp_ram"], emcp_nand=snap["emcp_nand"], is_emcp=snap["is_emcp"],
                interface=snap["interface"], classification_source=snap["classification_source"],
                last_updated=snap["last_updated"])

        n = 0
        with transaction.atomic():
            for op in reversed(log.get("ops", [])):
                if op["action"] in ("refresh", "rename"):
                    snap = op["before"]
                    if InventoryEntry.objects.filter(pk=snap["pk"]).exists():
                        restore_fields(snap["pk"], snap)
                        n += 1
                elif op["action"] == "merge":
                    w = op["wrong_snapshot"]
                    d = op["dst_before"]
                    # recria a entrada errada
                    obj, created = InventoryEntry.objects.get_or_create(
                        lot=lot, part_number=w["part_number"],
                        defaults=dict(quantity=w["quantity"], chip_type=w["chip_type"],
                                      brand=w["brand"], capacity=w["capacity"], emcp_ram=w["emcp_ram"],
                                      emcp_nand=w["emcp_nand"], is_emcp=w["is_emcp"],
                                      interface=w["interface"], classification_source=w["classification_source"]))
                    if created:
                        InventoryEntry.objects.filter(pk=obj.pk).update(
                            added_at=w["added_at"], last_updated=w["last_updated"])
                    # restaura o destino ao estado anterior
                    if InventoryEntry.objects.filter(pk=d["pk"]).exists():
                        restore_fields(d["pk"], d)
                    n += 1

        os.rename(path, path + ".done")
        self.stdout.write(self.style.SUCCESS(f"✅ Revertido: {n} operação(ões). Log → {path}.done"))
