"""
fix_capacities_and_brands.py — Corrige dois problemas no banco Micron
======================================================================

FIX 1 — Capacities de RAM em formato Gb (bits) → MB/GB (bytes)
  Problema: import anterior tinha bug no _density_to_capacity (re.I fazia
  "4Gb" ser tratado como "4GB" e retornado sem conversão).
  Resultado: capacity='4Gb' em vez de '512MB', '8Gb' em vez de '1GB', etc.
  Solução: recalcula capacity para todos os KnownParts Micron RAM cujo campo
  capacity termina em 'Gb' (case-sensitive, b minúsculo = bits).
  Fórmula: 1 Gb = 128 MiB  →  threshold 1024 MiB = 1 GiB

FIX 2 — 9 registros SK Hynix com brand=Micron
  Prefixos: H9CKN, H9HCN, H9TKN
  Solução: altera brand para SK Hynix (cria brand se não existir).

Uso:
    python scripts/fix_capacities_and_brands.py
    python scripts/fix_capacities_and_brands.py --dry-run
"""

import os, sys, re, django, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q
from chips.models import KnownPart, Brand

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()
dry = args.dry_run

if dry:
    print("⚠  DRY RUN — nenhuma alteração será salva.\n")

counts = {"cap_updated": 0, "brand_updated": 0}

# ── Conversão Gb → MB/GB (mesma lógica corrigida do import_micron_catalog) ─────
_GB_BITS_RE = re.compile(r'^(\d+(?:\.\d+)?)Gb$')  # case-sensitive: Gb ≠ GB


def _recalc_capacity(cap_str: str) -> str:
    """Recalcula capacity a partir de um valor errado em Gb (bits)."""
    m = _GB_BITS_RE.match(cap_str)
    if not m:
        return ""  # não é um valor Gb — não deveria chegar aqui
    gb_val = float(m.group(1))
    mb_val = gb_val * 128          # 1 Gb = 128 MiB
    if mb_val < 1024:
        return f"{int(mb_val)}MB"
    g = mb_val / 1024
    return f"{int(g)}GB" if g == int(g) else f"{g:.1f}GB"


# ════════════════════════════════════════════════════════════════════════════
# FIX 1 — Recalcula capacities de RAM armazenadas em Gb
# ════════════════════════════════════════════════════════════════════════════
print("═" * 60)
print("FIX 1 — Recalcular capacities de RAM armazenadas em Gb (bits)")

# Registros Micron RAM cujo capacity termina em 'Gb' (formato bits, bug antigo)
wrong_caps = KnownPart.objects.filter(
    brand__name="Micron",
    chip_type="RAM",
).filter(
    Q(capacity__regex=r'^\d+(?:\.\d+)?Gb$')  # case-sensitive no SQLite
)

total_wrong = wrong_caps.count()
print(f"Registros com capacity em Gb: {total_wrong}\n")

# Agrupa por valor para mostrar preview
preview: dict[str, list] = {}
for kp in wrong_caps[:5]:
    new_cap = _recalc_capacity(kp.capacity)
    print(f"  [UPDATE] {kp.part_number[:50]:50s}  capacity: '{kp.capacity}' → '{new_cap}'")
if total_wrong > 5:
    print(f"  ... e mais {total_wrong - 5} registros")

print()

if not dry and total_wrong > 0:
    updated = 0
    for kp in wrong_caps.iterator(chunk_size=500):
        new_cap = _recalc_capacity(kp.capacity)
        if new_cap and new_cap != kp.capacity:
            kp.capacity = new_cap
            kp.save(update_fields=["capacity", "last_updated"])
            updated += 1
    counts["cap_updated"] = updated
    print(f"✅ {updated} capacities corrigidas.")
elif dry:
    counts["cap_updated"] = total_wrong
    print(f"  (dry-run: {total_wrong} seriam atualizadas)")


# ════════════════════════════════════════════════════════════════════════════
# FIX 2 — Corrigir brand dos 9 registros SK Hynix
# ════════════════════════════════════════════════════════════════════════════
print()
print("═" * 60)
print("FIX 2 — Corrigir brand de registros SK Hynix (brand=Micron incorreto)")

SK_PREFIXES = ("H9CKN", "H9HCN", "H9TKN")

hynix_parts = KnownPart.objects.filter(
    brand__name="Micron",
    part_number__regex=r'^H9[A-Z]{2,3}',
).filter(
    Q(part_number__startswith="H9CKN") |
    Q(part_number__startswith="H9HCN") |
    Q(part_number__startswith="H9TKN")
)

total_hynix = hynix_parts.count()
print(f"Registros SK Hynix com brand=Micron: {total_hynix}\n")

for kp in hynix_parts:
    print(f"  [UPDATE] id={kp.id:5d}  PN={kp.part_number[:40]:40s}  brand: Micron → SK Hynix")

print()

if not dry and total_hynix > 0:
    # Garante que a brand SK Hynix existe
    hynix_brand, created = Brand.objects.get_or_create(
        name="SK Hynix",
        defaults={"code": "SKH"},
    )
    if created:
        print(f"  Brand 'SK Hynix' criada (id={hynix_brand.id}).")
    else:
        print(f"  Brand 'SK Hynix' já existe (id={hynix_brand.id}).")

    updated = hynix_parts.update(brand=hynix_brand)
    counts["brand_updated"] = updated
    print(f"✅ {updated} registros movidos para brand=SK Hynix.")
elif dry:
    counts["brand_updated"] = total_hynix
    print(f"  (dry-run: {total_hynix} seriam atualizados)")


# ── Relatório final ────────────────────────────────────────────────────────
print()
print("═" * 60)
print("✅  Concluído.")
print(f"   Capacities recalculadas: {counts['cap_updated']}")
print(f"   Brands corrigidas:       {counts['brand_updated']}")

if dry:
    print("\n⚠  DRY RUN — nenhuma alteração foi salva.")
else:
    try:
        from chips.engine import clear_engine_cache
        clear_engine_cache()
        print("   🗑  Cache do engine invalidado.")
    except Exception as e:
        print(f"   ⚠  Cache não invalidado: {e}")
