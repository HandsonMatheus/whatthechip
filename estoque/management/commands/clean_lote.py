"""
clean_lote
==========
Remove de um lote as entradas CONTAMINADAS — PNs que o operador introduziu numa
data e que NÃO são confirmados no banco (classification_source != "banco de dados"
e confidence != confirmed/manual). Tipicamente erros de digitação ou chips que
ainda não deviam ter entrado no estoque.

POR QUE usa `added_at` e não a planilha:
O Excel exporta `last_updated` (muda a cada reposição), então não distingue um
chip da base reposto hoje de um PN novo digitado hoje. Já `added_at` (auto_now_add)
é a data REAL de criação da entrada — um restock só mexe em `last_updated`, nunca
em `added_at`. Logo `added_at >= --since` isola exatamente os PNs introduzidos no
período, em qualquer quantidade (pega também o typo lançado com Qtd > 1, que a
planilha esconde).

O que é considerado CONTAMINAÇÃO (alvo da remoção):
  added_at >= --since   E   não-confirmado
onde "não-confirmado" = classification_source not in ("banco de dados",)
E, por segurança, o PN é reclassificado agora: se hoje ele bate como
confirmed/manual no engine, é POUPADO (não remove um chip que já foi confirmado).

Nunca remove:
  - entradas confirmadas (banco de dados / confidence confirmed|manual);
  - entradas anteriores a --since (a base legítima);
  - PNs listados em --keep.

Regra de ouro #1: este comando ESCREVE no banco -> roda em --dry-run por padrão.
Reversível: o --commit grava um snapshot completo das linhas removidas
(clean_lote_<N>_revert.json em BASE_DIR); --revert recria as entradas idênticas.

Uso (apontando DATABASE_URL para o Postgres do Render — ver DEPLOY_RENDER.md):
    python manage.py clean_lote                         # dry-run lote 39, desde 2026-06-16
    python manage.py clean_lote --lot 39 --since 2026-06-16
    python manage.py clean_lote --keep KLMCG2UCTA,KLMBG4GEND   # poupa PNs legítimos
    python manage.py clean_lote --commit                # aplica a remoção
    python manage.py clean_lote --revert                # desfaz o último --commit
"""

import json
import os
from datetime import datetime, time
from difflib import get_close_matches

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from estoque.models import InventoryEntry, Lot

DEFAULT_LOT = 39
DEFAULT_SINCE = "2026-06-16"
CONFIRMED_SOURCES = {"banco de dados"}
CONFIRMED_CONF = {"confirmed", "manual"}


def _revert_path(lot_number):
    return os.path.join(str(settings.BASE_DIR), f"clean_lote_{lot_number:03d}_revert.json")


class Command(SafeWriteCommand):
    help = "Remove entradas contaminadas (PNs novos não confirmados) de um lote. Dry-run por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=DEFAULT_LOT)
        parser.add_argument("--since", type=str, default=DEFAULT_SINCE,
                            help="Data (YYYY-MM-DD) — só entradas criadas a partir dela são candidatas.")
        parser.add_argument("--keep", type=str, default="",
                            help="PNs a POUPAR, separados por vírgula (ex.: KLMCG2UCTA,KLMBG4GEND).")
        parser.add_argument("--commit", action="store_true",
                            help="Aplica a remoção. Sem isso, só simula (dry-run).")
        parser.add_argument("--revert", action="store_true",
                            help="Recria as entradas do último --commit (lê o JSON de revert).")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_lot(self, lot_number):
        try:
            return Lot.objects.get(number=lot_number)
        except Lot.DoesNotExist:
            raise CommandError(f"Lote #{lot_number:03d} não existe.")

    def _is_confirmed_now(self, pn):
        """Reclassifica o PN agora; True se o engine o tem como confirmed/manual."""
        try:
            from chips.engine import classify
            r = classify(pn) or {}
            return (
                r.get("classification_source") in CONFIRMED_SOURCES
                or r.get("confidence") in CONFIRMED_CONF
            )
        except Exception:
            # Sem engine disponível, cai para o campo gravado (já filtrado antes).
            return False

    # ── main ──────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["lot"])

        lot = self._get_lot(opts["lot"])
        commit = opts["commit"]
        lot_number = opts["lot"]
        keep = {p.strip().upper() for p in opts["keep"].split(",") if p.strip()}

        try:
            since_date = datetime.strptime(opts["since"], "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("--since deve estar no formato YYYY-MM-DD.")
        since_dt = timezone.make_aware(datetime.combine(since_date, time.min))

        # "Conjunto abençoado": a base legítima do lote (pré-período + confirmados).
        # Usado só para sugerir de qual chip real cada suspeito parece ser typo.
        blessed = sorted({
            e.part_number for e in lot.entries.all()
            if e.added_at < since_dt or e.classification_source in CONFIRMED_SOURCES
        })

        # Candidatos: criados no período E não confirmados pela fonte gravada.
        candidates = list(
            lot.entries.filter(added_at__gte=since_dt)
            .exclude(classification_source__in=CONFIRMED_SOURCES)
            .order_by("part_number")
        )

        targets, spared = [], []
        for e in candidates:
            if e.part_number in keep:
                spared.append((e, "—keep"))
            elif self._is_confirmed_now(e.part_number):
                spared.append((e, "confirmado agora no engine"))
            else:
                near = get_close_matches(e.part_number, [b for b in blessed if b != e.part_number],
                                         n=1, cutoff=0.8)
                targets.append((e, near[0] if near else ""))

        # ── relatório ─────────────────────────────────────────────────────────
        mode = self.style.SUCCESS("COMMIT (grava)") if commit \
            else self.style.WARNING("DRY-RUN (não grava — use --commit)")
        self.stdout.write("")
        self.stdout.write(f"Lote #{lot_number:03d}  ·  operador: {lot.operator}  ·  desde: {since_date}  ·  modo: {mode}")
        self.stdout.write("=" * 92)
        self.stdout.write(f"{'PART NUMBER':<20}{'QTD':>4}  {'FONTE':<16}{'PROVÁVEL TYPO DE':<20}")
        self.stdout.write("-" * 92)
        total_qty = 0
        for e, near in targets:
            total_qty += e.quantity
            hint = self.style.WARNING(near) if near else self.style.ERROR("(PN novo — revisar)")
            self.stdout.write(f"{e.part_number:<20}{e.quantity:>4}  {(e.classification_source or '—'):<16}{hint}")
        self.stdout.write("-" * 92)
        self.stdout.write(
            f"A REMOVER: {self.style.ERROR(str(len(targets)))} entrada(s)  ·  {total_qty} chip(s).  "
            f"Poupadas: {len(spared)}.")

        if spared:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Poupadas (não removidas):"))
            for e, why in spared:
                self.stdout.write(f"    {e.part_number:<20} {e.quantity:>4}   ({why})")

        if not targets:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Nada a remover com os critérios atuais."))
            return

        if not commit:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: nada removido. Revise a lista, proteja legítimos com "
                "--keep PN1,PN2 e rode com --commit."))
            return

        # ── commit (atômico) ───────────────────────────────────────────────────
        log = {"lot": lot_number, "ts": datetime.now().isoformat(),
               "since": opts["since"], "removed": []}
        with transaction.atomic():
            for e, near in targets:
                log["removed"].append({
                    "part_number": e.part_number, "quantity": e.quantity,
                    "chip_type": e.chip_type, "brand": e.brand, "capacity": e.capacity,
                    "emcp_ram": e.emcp_ram, "emcp_nand": e.emcp_nand, "is_emcp": e.is_emcp,
                    "interface": e.interface, "classification_source": e.classification_source,
                    "added_at": e.added_at.isoformat(), "last_updated": e.last_updated.isoformat(),
                })
                e.delete()

        path = _revert_path(lot_number)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=2)

        new_total = sum(e.quantity for e in lot.entries.all())
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ {len(log['removed'])} entrada(s) removida(s) ({total_qty} chips). "
            f"Lote #{lot_number:03d} agora soma {new_total} chips."))
        self.stdout.write(f"   Snapshot de reversão: {path}")
        self.stdout.write(f"   Desfazer: python manage.py clean_lote --lot {lot_number} --revert")

    # ── revert ──────────────────────────────────────────────────────────────────

    def _revert(self, lot_number):
        path = _revert_path(lot_number)
        if not os.path.exists(path):
            raise CommandError(f"Snapshot de reversão não encontrado em {path}. Nada a desfazer.")
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
        lot = self._get_lot(lot_number)

        restored = 0
        with transaction.atomic():
            for rec in log.get("removed", []):
                obj, created = InventoryEntry.objects.get_or_create(
                    lot=lot, part_number=rec["part_number"],
                    defaults={
                        "chip_type": rec["chip_type"], "brand": rec["brand"],
                        "capacity": rec["capacity"], "emcp_ram": rec["emcp_ram"],
                        "emcp_nand": rec["emcp_nand"], "is_emcp": rec["is_emcp"],
                        "interface": rec["interface"],
                        "classification_source": rec["classification_source"],
                        "quantity": rec["quantity"],
                    },
                )
                if created:
                    # auto_now_add/auto_now ignoram valores no create -> restaura via update.
                    InventoryEntry.objects.filter(pk=obj.pk).update(
                        added_at=rec["added_at"], last_updated=rec["last_updated"])
                    restored += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  {rec['part_number']} já existe no lote — pulado (não duplico)."))

        os.rename(path, path + ".done")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Revertido: {restored} entrada(s) recriada(s). Snapshot arquivado em {path}.done"))
