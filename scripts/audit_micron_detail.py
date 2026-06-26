"""
audit_micron_detail.py — Inspeciona os registros problemáticos em detalhe
Uso: python scripts/audit_micron_detail.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q
from chips.models import KnownPart

qs = KnownPart.objects.filter(brand__name="Micron")

def empty_q(field):
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})

# ── 1. Os 2 registros sem FBGA ────────────────────────────────────────────────
print("=== SEM FBGA CODE (2 registros) ===")
for kp in qs.filter(empty_q("fbga_code")):
    print(f"  id={kp.id}  PN={kp.part_number}")
    print(f"    chip_type={kp.chip_type}  subtype={kp.subtype}")
    print(f"    confidence={kp.confidence}")
    print(f"    capacity={kp.capacity}  density={kp.density_gbit}")
    print(f"    source_url={kp.source_url}")
    print()

# ── 2. Registro com subtype "LPDDR4 standalone" ───────────────────────────────
print("=== SUBTYPE 'LPDDR4 standalone' ===")
for kp in qs.filter(subtype__icontains="standalone"):
    print(f"  id={kp.id}  PN={kp.part_number}")
    print(f"    chip_type={kp.chip_type}  subtype='{kp.subtype}'")
    print(f"    fbga={kp.fbga_code}  capacity={kp.capacity}  density={kp.density_gbit}")
    print()

# ── 3. Os 2 registros com density '16GB' ─────────────────────────────────────
print("=== DENSITY '16GB' (deveria ser Gb?) ===")
for kp in qs.filter(density_gbit="16GB"):
    print(f"  id={kp.id}  PN={kp.part_number}")
    print(f"    chip_type={kp.chip_type}  subtype={kp.subtype}")
    print(f"    density_gbit='{kp.density_gbit}'  capacity='{kp.capacity}'")
    print(f"    interface={kp.interface}")
    print(f"    source_url={kp.source_url}")
    print()

# ── 4. Registros NÃO confirmados (engine ignora — confidence != confirmed/manual) ──
print("=== CONFIDENCE NÃO-CONFIRMED (engine ignora) ===")
for kp in qs.exclude(confidence__in=("confirmed", "manual")):
    print(f"  id={kp.id}  PN={kp.part_number}  confidence={kp.confidence}")
    print(f"    chip_type={kp.chip_type}  subtype={kp.subtype}  fbga={kp.fbga_code}")
    print()

# ── 5. Amostra dos registros sem capacity — padrão DC ────────────────────────
print("=== AMOSTRA SEM CAPACITY — PADRÃO '-DC' ===")
dc_parts = qs.filter(empty_q("capacity"), part_number__contains="-DC")
print(f"Total com '-DC' e sem capacity: {dc_parts.count()}")
for kp in dc_parts[:20]:
    print(f"  PN={kp.part_number}")
    print(f"    fbga={kp.fbga_code}  chip_type={kp.chip_type}  subtype={kp.subtype}")
    print()

# ── 6. Registros sem capacity mas SEM '-DC' ───────────────────────────────────
print("=== SEM CAPACITY e SEM '-DC' (outros casos) ===")
non_dc = qs.filter(empty_q("capacity")).exclude(part_number__contains="-DC")
print(f"Total: {non_dc.count()}")
for kp in non_dc[:15]:
    print(f"  PN={kp.part_number}")
    print(f"    fbga={kp.fbga_code}  chip_type={kp.chip_type}  subtype={kp.subtype}")
    print()

# ── 7. Subtipos únicos nas RAM sem subtype ────────────────────────────────────
print("=== RAM SEM SUBTYPE — prefixos únicos de PN ===")
no_sub_ram = qs.filter(chip_type="RAM", subtype="").values_list("part_number", flat=True)
prefixes = {}
for pn in no_sub_ram:
    prefix = pn[:7]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1
for p, n in sorted(prefixes.items(), key=lambda x: -x[1]):
    print(f"  {p}: {n}")

print("\nDone.")
