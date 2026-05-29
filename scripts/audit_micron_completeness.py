"""
audit_micron_completeness.py — Panorama de completude do banco Micron
=====================================================================
Mostra, por chip_type/subtype, quantos registros têm cada campo preenchido.
Uso: python scripts/audit_micron_completeness.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q, Count
from chips.models import KnownPart

qs = KnownPart.objects.filter(brand__name="Micron")
total = qs.count()

def empty_q(field):
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})

def pct(n, of):
    return f"{n/of*100:.0f}%" if of else "0%"

print(f"\n{'='*70}")
print(f"  COMPLETUDE DO BANCO MICRON — {total} KnownParts")
print(f"{'='*70}")

# ── 1. Visão geral por campo ──────────────────────────────────────────────
FIELDS = [
    ("fbga_code",    "FBGA Code"),
    ("chip_type",    "chip_type"),
    ("subtype",      "subtype"),
    ("capacity",     "capacity"),
    ("density_gbit", "density_gbit"),
    ("interface",    "interface"),
    ("notes",        "notes"),
]

print("\n── COMPLETUDE GERAL ──────────────────────────────────────────────────")
print(f"  {'Campo':<16}  {'Preenchido':>10}  {'Vazio':>8}  {'% OK':>6}")
print(f"  {'-'*16}  {'-'*10}  {'-'*8}  {'-'*6}")
for field, label in FIELDS:
    empty = qs.filter(empty_q(field)).count()
    filled = total - empty
    print(f"  {label:<16}  {filled:>10}  {empty:>8}  {pct(filled, total):>6}")

# ── 2. Breakdown por chip_type/subtype ────────────────────────────────────
print("\n── BREAKDOWN POR TIPO — campos críticos (capacity + interface) ────────")
print(f"\n  {'chip_type':<8} {'subtype':<10} {'total':>6} {'cap OK':>7} {'iface OK':>9} {'notes OK':>9}")
print(f"  {'-'*8} {'-'*10} {'-'*6} {'-'*7} {'-'*9} {'-'*9}")

for row in (
    qs.values("chip_type", "subtype")
    .annotate(n=Count("id"))
    .order_by("chip_type", "subtype")
):
    ct = row["chip_type"] or "(vazio)"
    st = row["subtype"]   or "(vazio)"
    n  = row["n"]

    sub_qs = qs.filter(chip_type=row["chip_type"], subtype=row["subtype"])
    cap_ok   = sub_qs.exclude(empty_q("capacity")).count()
    iface_ok = sub_qs.exclude(empty_q("interface")).count()
    notes_ok = sub_qs.exclude(empty_q("notes")).count()

    cap_flag   = "✅" if cap_ok   == n else ("⚠ " if cap_ok   > 0 else "❌")
    iface_flag = "✅" if iface_ok == n else ("⚠ " if iface_ok > 0 else "❌")
    notes_flag = "✅" if notes_ok == n else ("⚠ " if notes_ok > 0 else "❌")

    print(
        f"  {ct:<8} {st:<10} {n:>6}   "
        f"{cap_flag} {cap_ok:>4}   {iface_flag} {iface_ok:>6}   {notes_flag} {notes_ok:>6}"
    )

# ── 3. Registros completamente sem dados úteis (capacity + interface + notes)
print("\n── REGISTROS COM capacity + interface + notes TODOS VAZIOS ───────────")
hollow = qs.filter(empty_q("capacity"), empty_q("interface"), empty_q("notes"))
print(f"  Total: {hollow.count()}")

by_type = {}
for kp in hollow:
    key = f"{kp.chip_type}/{kp.subtype or '?'}"
    by_type[key] = by_type.get(key, 0) + 1
for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f"  {k:<20}  {v}")

# ── 4. Amostras de registros sem capacity (por tipo) ─────────────────────
print("\n── AMOSTRAS SEM CAPACITY (até 5 por tipo) ────────────────────────────")
for ct in ["RAM", "eMMC", "UFS", "eMCP", "uMCP"]:
    no_cap = qs.filter(chip_type=ct).filter(empty_q("capacity"))
    if no_cap.exists():
        print(f"\n  [{ct}] sem capacity: {no_cap.count()} registros")
        for kp in no_cap[:5]:
            print(f"    PN={kp.part_number}  fbga={kp.fbga_code}  density={kp.density_gbit or '-'}")

print(f"\n{'='*70}\n")
