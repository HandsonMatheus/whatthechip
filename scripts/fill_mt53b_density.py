"""
fill_mt53b_density.py — Calcula density_gbit e capacity para registros MT53x
=============================================================================
Os registros MT53B/D/E (LPDDR4/LPDDR4X) não constam nos CSVs da Micron, portanto
density_gbit e capacity ficaram vazios após a importação e correção de tipo.

Fórmula derivada do naming convention Micron LPDDR:
    MT53x {rows}[M|G]{bus}D{dies}{suffix}
    • M = Mega (×1)     → density_gbit = rows × bus × dies / 1024
    • G = Giga (×1024)  → density_gbit = rows × 1024 × bus × dies / 1024
                                       = rows × bus × dies
    capacity_gb = density_gbit / 8

Verificação com dado do CSV (MT53B128M32D1DT = "4Gb"):
    128 × 32 × 1 / 1024 = 4.0 Gbit ✓

Verificação para notação G (MT53E1G32D2FW):
    1 × 1024 × 32 × 2 / 1024 = 64 Gbit = 8GB ✓

Uso:
    python scripts/fill_mt53b_density.py
    python scripts/fill_mt53b_density.py --dry-run
"""
import os, sys, re, django, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import KnownPart

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()
dry = args.dry_run

if dry:
    print("⚠  DRY RUN — nenhuma alteração será salva.\n")

# Regex: MT53x <rows>[M|G]<bus>D<dies><suffix>
# Ex: MT53B512M32D2NP → rows=512, unit=M, bus=32, dies=2
# Ex: MT53E1G32D2FW   → rows=1,   unit=G, bus=32, dies=2
_PN_RE = re.compile(r'^MT53[A-Z](\d+)([MG])(\d+)D(\d+)', re.IGNORECASE)

qs = KnownPart.objects.filter(
    brand__name="Micron",
    part_number__startswith="MT53",
    chip_type="RAM",
)

print(f"Registros MT53 RAM encontrados: {qs.count()}\n")
print(f"  {'PN':<45}  {'density_gbit':>12}  {'capacity':>10}  {'status':>10}")
print(f"  {'-'*45}  {'-'*12}  {'-'*10}  {'-'*10}")

updated = skipped = errors = 0

for kp in qs.order_by("part_number"):
    m = _PN_RE.match(kp.part_number)
    if not m:
        print(f"  ⚠  PN sem match no regex: {kp.part_number}")
        errors += 1
        continue

    rows      = int(m.group(1))
    unit      = m.group(2).upper()   # 'M' ou 'G'
    bus       = int(m.group(3))
    dies      = int(m.group(4))

    # G = Giga = 1024M  →  multiplicador 1024; M = multiplicador 1
    row_mult  = 1024 if unit == 'G' else 1
    density_gbit = rows * row_mult * bus * dies / 1024   # base-2

    # Arredonda para inteiro se for exato, senão 1 casa decimal
    if density_gbit == int(density_gbit):
        density_str = f"{int(density_gbit)} Gb"
        density_val = int(density_gbit)
    else:
        density_str = f"{density_gbit:.2f} Gb"
        density_val = density_gbit

    # Capacity em GB (se exato) ou MB
    cap_bytes_gb = density_val / 8
    if cap_bytes_gb >= 1 and cap_bytes_gb == int(cap_bytes_gb):
        capacity = f"{int(cap_bytes_gb)}GB"
    elif cap_bytes_gb >= 1:
        capacity = f"{cap_bytes_gb:.2f}GB"
    else:
        capacity = f"{int(cap_bytes_gb * 1024)}MB"

    already_ok = (
        kp.density_gbit == density_val and
        kp.capacity == capacity
    )

    status = "OK (skip)" if already_ok else ("DRY" if dry else "UPDATE")
    print(f"  {kp.part_number:<45}  {density_str:>12}  {capacity:>10}  {status:>10}")

    if already_ok:
        skipped += 1
        continue

    if not dry:
        kp.density_gbit = density_val
        kp.capacity     = capacity
        kp.save(update_fields=["density_gbit", "capacity", "last_updated"])

    updated += 1

print()
if dry:
    print(f"⚠  DRY RUN — {updated} seriam atualizados, {skipped} já corretos, {errors} erros.")
else:
    print(f"✅ {updated} registros atualizados, {skipped} já corretos, {errors} erros.")
    if updated > 0:
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            print("   🗑  Cache do engine invalidado.")
        except Exception as e:
            print(f"   ⚠  Cache não invalidado: {e}")
