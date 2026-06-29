"""
validate_convention — READ-ONLY. Sinaliza registros que fogem da convenção única
(chips/chip_types.py). NÃO escreve nada. Rodar antes de alinhar populate_*/migrar.

Categorias:
  conforme      — chip_type já é o token canônico (nada a fazer)
  migrar        — chip_type resolve limpo p/ um token específico (migração mecânica)
  ambiguo       — genérico SEM geração recuperável (multi-geração) → DECISÃO do usuário
  conflito      — chip_type (DRAM específico) × subtype dizem famílias diferentes
                  (ex.: chip_type="RDRAM" + subtype="DDR5") → DECISÃO do usuário
  desconhecido  — chip_type fora do vocabulário → DECISÃO do usuário

    python manage.py validate_convention             # resumo
    python manage.py validate_convention --list       # lista os que exigem DECISÃO
    python manage.py validate_convention --families   # valida ChipFamily também
"""
import collections

from django.core.management.base import BaseCommand

from chips.chip_types import canonical_chip_type, is_generic, label_kind, spec_for
from chips.conventions import canonical_gen
from chips.management.commands.normalize_convention import _FAMILY_GENERIC, _multi_gen
from chips.models import ChipFamily, KnownPart

_DRAM_CATS = {"dram_pc", "dram_mobile", "dram_gpu", "dram_legacy"}


def _conflict(chip_type: str, subtype: str):
    """(ct_token, st_token) se o chip_type (DRAM específico) conflita com a família
    de geração do subtype; senão None. Gerenciada/NAND/catálogo nunca conflitam
    (subtype é geração LPDDR / célula / descritivo)."""
    ct_alone = canonical_chip_type(chip_type, "")
    s = spec_for(ct_alone)
    if not s or s.generic or s.category not in _DRAM_CATS:
        return None
    st_gen = canonical_gen(subtype or "")
    st = spec_for(st_gen) if st_gen else None
    if st and not st.generic and st.category in _DRAM_CATS \
       and label_kind(ct_alone) != label_kind(st_gen):
        return (ct_alone, st_gen)
    return None


def categorize(chip_type: str, subtype: str):
    ct = (chip_type or "").strip()
    conf = _conflict(ct, subtype)
    if conf:
        return "conflito", f"{conf[0]} × {conf[1]}"
    if not ct:
        return "desconhecido", "(chip_type vazio)"
    canon = canonical_chip_type(ct, subtype or "")
    # multi-geracao (ex.: K3 "LPDDR2/LPDDR3") -> generico, igual ao normalize_convention.
    if _multi_gen(subtype or "") and not is_generic(canon):
        canon = _FAMILY_GENERIC.get(label_kind(canon), canon)
    if spec_for(canon) is None:
        return "desconhecido", canon
    if is_generic(canon):
        return "ambiguo", canon
    if ct == canon:
        return "conforme", canon
    return "migrar", f"{ct} → {canon}"


class Command(BaseCommand):
    help = "Valida a conformidade dos registros com a convenção única (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="Lista os que exigem DECISÃO")
        parser.add_argument("--families", action="store_true", help="Valida ChipFamily também")

    def handle(self, *args, **opts):
        cats = collections.Counter()
        decisions = collections.defaultdict(list)
        migrar = collections.Counter()

        for kp in KnownPart.objects.select_related("brand").iterator():
            cat, detail = categorize(kp.chip_type, kp.subtype)
            cats[cat] += 1
            if cat in ("conflito", "ambiguo", "desconhecido"):
                decisions[cat].append(
                    (kp.brand.name if kp.brand_id else "", kp.chip_type or "", kp.subtype or "", detail, kp.part_number)
                )
            elif cat == "migrar":
                migrar[detail] += 1

        total = sum(cats.values())
        self.stdout.write(f"\n=== validate_convention — {total} KnownParts ===")
        for c in ("conforme", "migrar", "ambiguo", "conflito", "desconhecido"):
            self.stdout.write(f"  {c:14s} {cats.get(c, 0)}")
        need = cats.get("conflito", 0) + cats.get("ambiguo", 0) + cats.get("desconhecido", 0)
        self.stdout.write(f"\n  >>> EXIGEM DECISAO DO USUARIO: {need}")

        self.stdout.write("\n  migrações mecânicas (top 20):")
        for k, c in migrar.most_common(20):
            self.stdout.write(f"    [{c:5d}x] {k}")

        if opts["list"]:
            for cat in ("conflito", "desconhecido", "ambiguo"):
                rows = decisions[cat]
                if not rows:
                    continue
                self.stdout.write(f"\n--- {cat.upper()} ({len(rows)}) — DECIDIR ---")
                grouped = collections.Counter()
                example = {}
                for brand, ct, st, detail, pn in rows:
                    key = (brand, ct, st[:40], detail)
                    grouped[key] += 1
                    example.setdefault(key, pn)
                for (brand, ct, st, detail), cnt in grouped.most_common():
                    self.stdout.write(
                        f"    [{cnt:4d}x] {brand:10s} chip_type={ct!r} subtype={st!r} → {detail}  (ex.: {example[(brand, ct, st, detail)]})"
                    )

        if opts["families"]:
            self.stdout.write("\n=== ChipFamily ===")
            fcats = collections.Counter()
            flag = []
            for f in ChipFamily.objects.filter(active=True).select_related("brand"):
                cat, detail = categorize(f.chip_type, f.subtype)
                fcats[cat] += 1
                if cat in ("conflito", "ambiguo", "desconhecido", "migrar"):
                    flag.append((cat, f.brand.name, f.prefix, f.chip_type or "", detail))
            self.stdout.write(f"  {dict(fcats)}")
            for cat, brand, prefix, ct, detail in sorted(flag):
                self.stdout.write(f"    {cat:12s} {brand:10s} {prefix:8s} chip_type={ct!r} → {detail}")
