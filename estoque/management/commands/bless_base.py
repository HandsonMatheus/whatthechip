"""
bless_base
==========
"Abençoa" a base atual de estoque: promove a KnownPart CONFIRMADO (confidence=
"manual", status="enriched") cada Part Number que o operador JÁ tinha lançado
antes de uma data de corte. É a ponte para ligar o bloqueio "só confirmados" no
add_chip sem travar a reposição dos chips comuns legítimos.

POR QUE "manual" e não "confirmed":
A pirâmide de confiança (regra de ouro #6) reserva "confirmed" para verificação
por datasheet/Octopart. "manual" significa "um humano avalizou" — exatamente o
caso: você carregou esses PNs deliberadamente como a base. Não suja o topo da
pirâmide e ainda assim VENCE a gramática no engine (human_verified).

O que faz, por PN distinto com added_at < --since (a base pré-corte):
  - se já existe KnownPart confirmed/manual  -> NÃO toca (regra: nunca rebaixar);
  - senão -> cria/atualiza KnownPart com os campos decodificados da entrada
    (chip_type, capacity, emcp_ram/nand, interface), status="enriched",
    confidence="manual", family casada pelo prefixo, brand pelo nome.

Regra de ouro #1: ESCREVE no banco -> dry-run por padrão.
Regra de ouro #3: após --commit em produção, REINICIE o servidor (cache do engine).
Reversível: --commit grava bless_base_revert.json (estado anterior de cada PN);
--revert remove os criados e restaura os que foram alterados.

Uso (DATABASE_URL apontando ao Render — ver DEPLOY_RENDER.md):
    python manage.py bless_base                       # dry-run, lote 39
    python manage.py bless_base --lot 39 --since 2026-06-16
    python manage.py bless_base --all-lots            # toda a base, qualquer lote
    python manage.py bless_base --commit              # aplica  (reinicie o servidor depois)
    python manage.py bless_base --revert              # desfaz o último --commit
"""

import json
import os
from datetime import datetime, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chips.models import Brand, KnownPart
from estoque.models import InventoryEntry, Lot

DEFAULT_LOT = 39
DEFAULT_SINCE = "2026-06-16"
PROTECTED_CONF = {"confirmed", "manual"}
REVERT_LOG = os.path.join(str(settings.BASE_DIR), "bless_base_revert.json")


class Command(BaseCommand):
    help = "Promove a base atual de estoque a KnownPart manual/enriched (ponte p/ o bloqueio). Dry-run por padrão."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=DEFAULT_LOT)
        parser.add_argument("--all-lots", action="store_true",
                            help="Considera entradas de TODOS os lotes, não só --lot.")
        parser.add_argument("--since", type=str, default=DEFAULT_SINCE,
                            help="Corte (YYYY-MM-DD): só PNs criados ANTES desta data são a base.")
        parser.add_argument("--confidence", type=str, default="manual",
                            choices=["manual", "confirmed"])
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--revert", action="store_true")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _brand_for(self, name):
        name = (name or "").strip() or "Desconhecida"
        b = Brand.objects.filter(name__iexact=name).first()
        if b:
            return b
        code = (name[:3] or "XXX").upper()
        while Brand.objects.filter(code=code).exists():
            code += "X"
        return Brand.objects.create(name=name, code=code,
                                    notes="Criada por bless_base (base do operador).")

    def _family_for(self, pn):
        try:
            from chips.engine import _match_family
            return _match_family(pn)
        except Exception:
            return None

    def _pick_entry(self, entries):
        # entrada mais representativa do PN: maior quantidade, desempate por pk.
        return max(entries, key=lambda e: (e.quantity, e.pk))

    # ── main ──────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert()

        try:
            since_date = datetime.strptime(opts["since"], "%Y-%m-%d").date()
        except ValueError:
            raise CommandError("--since deve estar no formato YYYY-MM-DD.")
        since_dt = timezone.make_aware(datetime.combine(since_date, time.min))
        conf = opts["confidence"]
        commit = opts["commit"]

        qs = InventoryEntry.objects.filter(added_at__lt=since_dt)
        if not opts["all_lots"]:
            try:
                lot = Lot.objects.get(number=opts["lot"])
            except Lot.DoesNotExist:
                raise CommandError(f"Lote #{opts['lot']:03d} não existe.")
            qs = qs.filter(lot=lot)

        # Agrupa por PN (um PN pode ter entradas em vários lotes).
        by_pn = {}
        for e in qs:
            by_pn.setdefault(e.part_number, []).append(e)

        to_create, to_update, skipped = [], [], []
        for pn, entries in sorted(by_pn.items()):
            existing = KnownPart.objects.filter(part_number=pn).first()
            if existing and existing.confidence in PROTECTED_CONF:
                skipped.append((pn, f"já {existing.confidence}"))
                continue
            (to_update if existing else to_create).append((pn, self._pick_entry(entries), existing))

        # ── relatório ─────────────────────────────────────────────────────────
        mode = self.style.SUCCESS("COMMIT (grava)") if commit \
            else self.style.WARNING("DRY-RUN (não grava — use --commit)")
        scope = "TODOS os lotes" if opts["all_lots"] else f"lote #{opts['lot']:03d}"
        self.stdout.write("")
        self.stdout.write(f"Abençoar base · {scope} · PNs criados antes de {since_date} · "
                          f"confidence={conf} · modo: {mode}")
        self.stdout.write("=" * 78)
        self.stdout.write(f"PNs distintos na base: {len(by_pn)}   "
                          f"criar: {self.style.SUCCESS(str(len(to_create)))}   "
                          f"atualizar: {len(to_update)}   "
                          f"poupados (já confirmados): {len(skipped)}")
        if to_create:
            self.stdout.write("")
            self.stdout.write("Serão CRIADOS como KnownPart manual/enriched:")
            for pn, e, _ in to_create[:60]:
                cap = e.capacity or (f"{e.emcp_nand} / {e.emcp_ram}".strip(" /")) or "—"
                self.stdout.write(f"    {pn:<20} {e.brand:<10} {e.chip_type:<8} {cap}")
            if len(to_create) > 60:
                self.stdout.write(f"    ... (+{len(to_create) - 60})")

        if not commit:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: nada gravado. Confira a lista e rode com --commit. "
                "Depois REINICIE o servidor (cache do engine)."))
            return

        # ── commit (atômico) ───────────────────────────────────────────────────
        log = {"ts": datetime.now().isoformat(), "confidence": conf,
               "created": [], "updated": []}
        with transaction.atomic():
            for pn, e, existing in to_create + to_update:
                fields = dict(
                    brand=self._brand_for(e.brand),
                    family=self._family_for(pn),
                    status="enriched",
                    chip_type=e.chip_type or "",
                    capacity=e.capacity or "",
                    emcp_ram=e.emcp_ram or "",
                    emcp_nand=e.emcp_nand or "",
                    interface=e.interface or "",
                    confidence=conf,
                    notes=f"Avalizado pela base do operador (carga inicial) via bless_base em {since_date}.",
                )
                if existing:
                    log["updated"].append({
                        "part_number": pn,
                        "prev_status": existing.status,
                        "prev_confidence": existing.confidence,
                    })
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    existing.save()
                else:
                    log["created"].append({"part_number": pn})
                    KnownPart.objects.create(part_number=pn, **fields)

        with open(REVERT_LOG, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=2)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ {len(log['created'])} criados, {len(log['updated'])} atualizados como "
            f"KnownPart {conf}/enriched."))
        self.stdout.write(self.style.WARNING(
            "⚠ REINICIE o servidor agora (o engine usa cache lru — regra de ouro #3)."))
        self.stdout.write(f"   Log de reversão: {REVERT_LOG}")
        self.stdout.write("   Desfazer: python manage.py bless_base --revert")

    # ── revert ──────────────────────────────────────────────────────────────────

    def _revert(self):
        if not os.path.exists(REVERT_LOG):
            raise CommandError(f"Log de reversão não encontrado em {REVERT_LOG}. Nada a desfazer.")
        with open(REVERT_LOG, encoding="utf-8") as fh:
            log = json.load(fh)

        removed = restored = 0
        with transaction.atomic():
            for rec in log.get("created", []):
                kp = KnownPart.objects.filter(part_number=rec["part_number"]).first()
                if kp:
                    kp.delete()
                    removed += 1
            for rec in log.get("updated", []):
                kp = KnownPart.objects.filter(part_number=rec["part_number"]).first()
                if kp:
                    kp.status = rec["prev_status"]
                    kp.confidence = rec["prev_confidence"]
                    kp.save(update_fields=["status", "confidence"])
                    restored += 1

        os.rename(REVERT_LOG, REVERT_LOG + ".done")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Revertido: {removed} KnownPart removidos, {restored} restaurados ao estado anterior."))
        self.stdout.write(self.style.WARNING(
            "⚠ REINICIE o servidor (cache do engine). Log arquivado em " + REVERT_LOG + ".done"))
