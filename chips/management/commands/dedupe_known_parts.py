"""
dedupe_known_parts.py
=====================
Passo 1A (parte 2): funde os KnownParts que normalizam para o MESMO
`part_number_norm` — as duplicatas cru-vs-normalizado (ex.: '08EMCP08-NL3DT227'
vs '08EMCP08NL3DT227', 'MT29C4G48MAZAPAKD-5 IT' vs 'MT29C4G48MAZAPAKD5IT').

MANTÉM o melhor (mesmo critério do engine: `_pick_best_known` — chip_type
preenchido > confiança > mais recente) e APAGA os demais. `KnownPart` NÃO tem
nenhuma FK de entrada (nada o referencia por FK; o estoque guarda part_number
como texto), então apagar é seguro — e a busca do engine resolve o part_number
do perdedor para o sobrevivente via `part_number_norm`. É o **pré-requisito** da
`UniqueConstraint(part_number_norm)` (migração 0015).

Dry-run por padrão. `--commit` grava (log de revert em `var/reverts/`).
`--revert` recria os apagados (só funciona ANTES da constraint 0015).

Uso:
    python manage.py dedupe_known_parts            # dry-run (mostra o plano)
    python manage.py dedupe_known_parts --commit
    python manage.py dedupe_known_parts --revert
"""

import collections
import json
import os

from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand

_REVERT_DIR = "var/reverts"
_REVERT = os.path.join(_REVERT_DIR, "dedupe_known_parts_revert.json")

# Campos do registro a salvar para o revert (recriar o apagado). Sem FKs além de brand.
_FIELDS = [
    "part_number", "chip_type", "subtype", "capacity", "density_gbit", "density_gb",
    "emcp_ram", "emcp_nand", "interface", "fbga_code", "device", "notes",
    "confidence", "source_url",
]


class Command(SafeWriteCommand):
    help = ("Funde duplicatas por part_number_norm (mantém o melhor, apaga o resto). "
            "Dry-run por padrão.")

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Grava (apaga os perdedores).")
        parser.add_argument("--revert", action="store_true", help="Recria os apagados pelo último --commit.")

    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert()

        from chips.models import KnownPart
        from chips.engine import _pick_best_known

        groups = collections.defaultdict(list)
        for kp in KnownPart.objects.all().select_related("brand"):
            groups[kp.part_number_norm].append(kp)
        colis = {k: v for k, v in groups.items() if len(v) > 1}

        self.stdout.write(
            f"\nColisões (norma com >1 PN): {len(colis)}  ·  "
            f"registros envolvidos: {sum(len(v) for v in colis.values())}")

        to_delete = []
        for norm, members in sorted(colis.items()):
            best = _pick_best_known(members)
            for m in members:
                if m.pk != best.pk:
                    to_delete.append(m)
                    self.stdout.write(
                        f"  manter '{best.part_number}'  ·  ✗ apagar '{m.part_number}' "
                        f"(conf={m.confidence}, type='{m.chip_type}')")

        if not to_delete:
            self.stdout.write(self.style.SUCCESS("Nada a fazer — sem colisões."))
            return
        if not opts["commit"]:
            self.stdout.write(self.style.WARNING(
                f"\nDRY-RUN: {len(to_delete)} registro(s) seriam apagados. Rode com --commit."))
            return

        log = [
            dict({f: getattr(m, f) for f in _FIELDS}, brand_code=m.brand.code)
            for m in to_delete
        ]
        with transaction.atomic():
            for m in to_delete:
                m.delete()
        os.makedirs(_REVERT_DIR, exist_ok=True)
        with open(_REVERT, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1)
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {len(to_delete)} apagado(s).  Revert: {_REVERT}  ·  "
            f"desfazer: python manage.py dedupe_known_parts --revert"))

    def _revert(self):
        from chips.models import Brand, KnownPart
        if not os.path.exists(_REVERT):
            raise CommandError(f"Revert não encontrado: {_REVERT}")
        with open(_REVERT, encoding="utf-8") as fh:
            log = json.load(fh)
        n = 0
        with transaction.atomic():
            for rec in log:
                code = rec.pop("brand_code")
                brand = Brand.objects.filter(code=code).first()
                if not brand:
                    continue
                KnownPart.objects.create(brand=brand, **rec)  # save() repreenche part_number_norm
                n += 1
        os.rename(_REVERT, _REVERT + ".done")
        self.stdout.write(self.style.SUCCESS(f"✅ {n} registro(s) recriado(s). Log → {_REVERT}.done"))
