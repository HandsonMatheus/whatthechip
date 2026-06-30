"""
normalize_convention — migra chip_type/subtype para a forma CANONICA (convencao
opcao 1: geracao no chip_type). DRY-RUN por padrao. REVERSIVEL (grava JSON com os
valores antigos antes de aplicar).

    python manage.py normalize_convention                 # dry-run (mostra o diff)
    python manage.py normalize_convention --commit         # aplica + grava JSON reversivel
    python manage.py normalize_convention --revert <json>  # desfaz

O que faz (idempotente):
  - ChipFamily.chip_type/subtype  -> canonico (RAM/DDR generico -> geracao especifica)
  - KnownPart.chip_type/subtype   -> canonico
  - Desativa familias Kingston bogus (KF/KVR/ACR — Kingston nao fabrica DRAM avulsa)
  - Familias MULTI-GERACAO (ex.: K3 "LPDDR2/LPDDR3") -> token generico (flagged), NAO
    forca uma geracao (decisao do usuario).

NAO mexe em: confidence (preserva confirmed/manual), capacity/density/emcp_* (specs).
Comportamento (label/rentabilidade) NAO muda — so o chip_type/subtype ARMAZENADO vira
canonico (o engine ja resolvia em tempo real via canonical_chip_type).
"""
import collections
import json
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from chips.chip_types import canonical_chip_type, is_generic, label_kind
from chips.conventions import canonical_gen
from chips.models import ChipFamily, KnownPart

# Kingston nao fabrica silicio; familias DRAM "KF/KVR/ACR" sao bogus (ver memoria
# k-prefix-bga-is-samsung). KVR=ValueRAM=modulos; ACR=marking de modulo.
BOGUS_KINGSTON_PREFIXES = {"KF", "KVR", "ACR"}

# Numeros de geracao por familia, p/ detectar multi-geracao (2 numeros distintos).
_GEN_NUM_RE = re.compile(r"(?:LP|G)?DDR(\d+)", re.I)
_FAMILY_GENERIC = {"lpddr": "LPDDR", "ddr": "DDR", "gddr": "GDDR"}


def _multi_gen(subtype: str) -> bool:
    """True se o subtype menciona 2+ numeros de geracao DISTINTOS (ex.: LPDDR2/LPDDR3).
    DDR3/DDR3L conta como UM (mesmo numero 3, variante L)."""
    nums = set(_GEN_NUM_RE.findall(subtype or ""))
    return len(nums) > 1


def _canon_subtype(canon_ct: str, subtype: str) -> str:
    """subtype canonico por tipo: DRAM=geracao; eMCP/uMCP=geracao LPDDR; eMMC/UFS=''; NAND=celula."""
    lk = label_kind(canon_ct)
    if lk in ("ddr", "lpddr", "gddr", "sdram", "rdram"):
        return canonical_gen(subtype or "") or (canon_ct if not is_generic(canon_ct) else (subtype or "").strip())
    if lk in ("emcp", "umcp"):
        return canonical_gen(subtype or "") or (subtype or "").strip()
    if lk in ("emmc", "ufs"):
        return ""
    if lk == "nand":
        return canonical_gen(subtype or "", "NAND Flash") or (subtype or "").strip()
    return (subtype or "").strip()


def _plan(obj):
    """Mudancas {campo: [old, new]} — APENAS chip_type (ou {} se nada muda).

    Migra SO o chip_type (o campo critico e persistido no estoque). O subtype NAO e
    migrado: e canonicalizado em tempo de LEITURA por canonical_gen (gateway/engine),
    e migrar o subtype da FAMILIA quebra a extracao de geracao do engine (eMCP) e
    perde info de familias multi-geracao (ex.: "LPDDR4X/5X"). Limpeza de subtype no
    write-time fica para os populate_* (nascer limpo), nao para esta migracao."""
    ct = (obj.chip_type or "").strip()
    st = (obj.subtype or "").strip()
    canon = canonical_chip_type(ct, st)
    # multi-geracao -> mantem generico (decisao do usuario), nao forca uma geracao
    if _multi_gen(st) and not is_generic(canon):
        canon = _FAMILY_GENERIC.get(label_kind(canon), canon)
    # KnownPart cujos campos proprios sao genericos: a FAMILIA e a autoridade da
    # geracao (o engine ja resolve por ela no classify) — usa o tipo canonico dela.
    fam = getattr(obj, "family", None)
    if is_generic(canon) and fam is not None:
        fam_canon = canonical_chip_type(fam.chip_type or "", fam.subtype or "")
        if not is_generic(fam_canon):
            canon = fam_canon
    ch = {}
    if canon != (obj.chip_type or ""):
        ch["chip_type"] = [obj.chip_type, canon]
    return ch


class Command(BaseCommand):
    help = "Migra chip_type/subtype para a convencao canonica (reversivel, dry-run por padrao)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Aplica (senao, dry-run).")
        parser.add_argument("--revert", type=str, default="", help="JSON de reversao a desfazer.")

    # ── revert ────────────────────────────────────────────────────────────────
    def _revert(self, path):
        log = json.load(open(path))
        with transaction.atomic():
            for e in log:
                Model = ChipFamily if e["model"] == "chipfamily" else KnownPart
                try:
                    obj = Model.objects.get(pk=e["pk"])
                except Model.DoesNotExist:
                    continue
                for field, (old, _new) in e["changes"].items():
                    setattr(obj, field, old)
                obj.save(update_fields=list(e["changes"].keys()))
        self.stdout.write(f"↩ revertido de {path} ({len(log)} registros).")

    # ── handle ──────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        if opts["revert"]:
            return self._revert(opts["revert"])

        revert_log = []
        ct_moves = collections.Counter()
        samples = []

        # Familias
        n_fam = n_deact = 0
        for f in ChipFamily.objects.select_related("brand"):
            ch = _plan(f)
            if ch:
                n_fam += 1
                revert_log.append({"model": "chipfamily", "pk": f.pk, "changes": ch})
                if "chip_type" in ch:
                    ct_moves[f"{ch['chip_type'][0]!r} -> {ch['chip_type'][1]!r}"] += 1
            if (f.brand and f.brand.name == "Kingston"
                    and f.prefix in BOGUS_KINGSTON_PREFIXES and f.active):
                n_deact += 1
                revert_log.append({"model": "chipfamily", "pk": f.pk,
                                   "changes": {"active": [True, False]}})

        # KnownParts
        n_kp = 0
        for kp in KnownPart.objects.select_related("family").iterator(chunk_size=1000):
            ch = _plan(kp)
            if ch:
                n_kp += 1
                revert_log.append({"model": "knownpart", "pk": kp.pk, "changes": ch})
                if "chip_type" in ch:
                    ct_moves[f"{ch['chip_type'][0]!r} -> {ch['chip_type'][1]!r}"] += 1
                if len(samples) < 12:
                    samples.append((kp.part_number, ch))

        self.stdout.write(f"\n=== normalize_convention ({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f"  Familias a migrar:        {n_fam}")
        self.stdout.write(f"  Familias Kingston a desativar (bogus): {n_deact}")
        self.stdout.write(f"  KnownParts a migrar:      {n_kp}")
        self.stdout.write("\n  chip_type — top movimentos:")
        for k, c in ct_moves.most_common(20):
            self.stdout.write(f"    [{c:5d}x] {k}")
        self.stdout.write("\n  amostra (KnownPart):")
        for pn, ch in samples:
            self.stdout.write(f"    {pn[:26]:26s} {ch}")

        if not opts["commit"]:
            self.stdout.write("\n[DRY-RUN] nada gravado. Rode com --commit para aplicar.")
            return

        with transaction.atomic():
            for e in revert_log:
                Model = ChipFamily if e["model"] == "chipfamily" else KnownPart
                obj = Model.objects.get(pk=e["pk"])
                for field, (_old, new) in e["changes"].items():
                    setattr(obj, field, new)
                obj.save(update_fields=list(e["changes"].keys()))

        path = "normalize_convention_revert.json"
        json.dump(revert_log, open(path, "w"), ensure_ascii=False, indent=0)
        self.stdout.write(f"\n✅ aplicado ({len(revert_log)} mudancas). Reversivel: {path}")
        self.stdout.write("   ↻ O cache do engine recarrega sozinho (catalog_version, passo 1B).")
