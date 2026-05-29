"""
audit_micron.py — Diagnóstico do banco de dados Micron
Uso: python scripts/audit_micron.py
"""

import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q, Count
from chips.models import KnownPart

qs = KnownPart.objects.filter(brand__name="Micron")
total = qs.count()

def pct(n): return f"{n/total*100:.1f}%" if total else "0%"

# ── 1. Campos vazios ──────────────────────────────────────────────────────────
def empty_q(field):
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})

e_fbga  = qs.filter(empty_q("fbga_code")).count()
e_cap   = qs.filter(empty_q("capacity")).count()
e_dens  = qs.filter(empty_q("density_gbit")).count()
e_iface = qs.filter(empty_q("interface")).count()
e_notes = qs.filter(empty_q("notes")).count()
e_sub   = qs.filter(empty_q("subtype")).count()
e_chip  = qs.filter(empty_q("chip_type")).count()

print(f"\n{'='*60}")
print(f"  AUDITORIA BANCO MICRON — {total} KnownParts")
print(f"{'='*60}")

print("\n── CAMPOS VAZIOS ─────────────────────────────────────────")
print(f"  fbga_code:    {e_fbga:4d}  {pct(e_fbga)}")
print(f"  capacity:     {e_cap:4d}  {pct(e_cap)}")
print(f"  density_gbit: {e_dens:4d}  {pct(e_dens)}")
print(f"  interface:    {e_iface:4d}  {pct(e_iface)}")
print(f"  notes:        {e_notes:4d}  {pct(e_notes)}")
print(f"  subtype:      {e_sub:4d}  {pct(e_sub)}")
print(f"  chip_type:    {e_chip:4d}  {pct(e_chip)}")

# ── 2. Breakdown chip_type / subtype ─────────────────────────────────────────
print("\n── CHIP_TYPE / SUBTYPE ───────────────────────────────────")
for row in qs.values("chip_type","subtype").annotate(n=Count("id")).order_by("-n"):
    ct = row["chip_type"] or "(vazio)"
    st = row["subtype"]   or "(vazio)"
    print(f"  {ct:10s} / {st:12s}  {row['n']:5d}")

# ── 3. Status e confidence ────────────────────────────────────────────────────
print("\n── STATUS ────────────────────────────────────────────────")
for row in qs.values("status").annotate(n=Count("id")).order_by("-n"):
    print(f"  {row['status']:20s}  {row['n']}")

print("\n── CONFIDENCE ────────────────────────────────────────────")
for row in qs.values("confidence").annotate(n=Count("id")).order_by("-n"):
    print(f"  {row['confidence']:20s}  {row['n']}")

# ── 4. Registros sem subtype (amostras) ──────────────────────────────────────
no_sub = qs.filter(empty_q("subtype")).order_by("part_number")[:20]
if no_sub:
    print(f"\n── AMOSTRAS SEM SUBTYPE (primeiros {no_sub.count()}) ────────────────")
    for kp in no_sub:
        print(f"  [{kp.chip_type or '?':10s}]  {kp.part_number}  cap={kp.capacity or '-'}  dens={kp.density_gbit or '-'}")

# ── 5. Registros sem capacity (amostras) ─────────────────────────────────────
no_cap = qs.filter(empty_q("capacity")).order_by("chip_type","subtype","part_number")[:20]
if no_cap:
    print(f"\n── AMOSTRAS SEM CAPACITY (primeiros 20) ─────────────────")
    for kp in no_cap:
        print(f"  [{kp.chip_type or '?':10s}/{kp.subtype or '?':10s}]  {kp.part_number}  dens={kp.density_gbit or '-'}")

# ── 6. FBGA duplicados ────────────────────────────────────────────────────────
from django.db.models import Count as C
dups = (
    KnownPart.objects
    .filter(brand__name="Micron")
    .exclude(Q(fbga_code="") | Q(fbga_code__isnull=True))
    .values("fbga_code")
    .annotate(n=C("id"))
    .filter(n__gt=1)
    .order_by("-n")
)
if dups:
    print(f"\n── FBGA DUPLICADOS ({dups.count()} casos) ─────────────────────")
    for row in dups[:15]:
        parts = list(KnownPart.objects.filter(fbga_code=row["fbga_code"]).values_list("part_number", flat=True))
        print(f"  {row['fbga_code']}  ({row['n']}x):  {' | '.join(parts)}")

# ── 7. Densidade estranha (non-standard values) ───────────────────────────────
print("\n── TOP DENSITY VALUES ───────────────────────────────────")
for row in (
    qs.exclude(empty_q("density_gbit"))
    .values("density_gbit")
    .annotate(n=Count("id"))
    .order_by("-n")[:20]
):
    print(f"  {row['density_gbit']:15s}  {row['n']}")

# ── 8. Interface estranha ─────────────────────────────────────────────────────
print("\n── TOP INTERFACE VALUES ─────────────────────────────────")
for row in (
    qs.exclude(empty_q("interface"))
    .values("interface")
    .annotate(n=Count("id"))
    .order_by("-n")[:15]
):
    print(f"  {row['interface']:40s}  {row['n']}")

print(f"\n{'='*60}\n")
