"""
fix_mt53b_misclassified.py — Corrige registros MT53B classificados erroneamente
=================================================================================
Causa: a API FBGA da Micron, ao ser consultada para um base PN eMMC/uMCP,
retorna também os dies LPDDR4 emparelhados (MT53B) do pacote MCP.
O import_micron_catalog criou esses dies com o chip_type do CSV (eMMC ou uMCP),
quando o correto é chip_type=RAM, subtype=LPDDR4.

Confirmação: source_url ID 4494 aponta para
  /products/obsolete/obsolete-lpddr4/part-catalog/part-detail/mt53b512m32d2np-...
  → Micron classifica MT53B512M32D2NP como LPDDR4.

Uso:
    python scripts/fix_mt53b_misclassified.py
    python scripts/fix_mt53b_misclassified.py --dry-run
"""
import os, sys, django, argparse
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

# Todos os KnownParts com prefixo MT53B que NÃO estão classificados como RAM
wrong = KnownPart.objects.filter(
    brand__name="Micron",
    part_number__startswith="MT53B",
).exclude(chip_type="RAM")

print(f"Registros MT53B com chip_type ≠ RAM: {wrong.count()}\n")

updated = 0
for kp in wrong:
    print(f"  [FIX] id={kp.id}  PN={kp.part_number}")
    print(f"        {kp.chip_type}/{kp.subtype or '(vazio)'} → RAM/LPDDR4")
    if not dry:
        kp.chip_type = "RAM"
        kp.subtype   = "LPDDR4"
        kp.save(update_fields=["chip_type", "subtype", "last_updated"])
    updated += 1

print()
if dry:
    print(f"⚠  DRY RUN — {updated} seriam corrigidos.")
else:
    print(f"✅ {updated} registros corrigidos.")
    try:
        from chips.engine import clear_engine_cache
        clear_engine_cache()
        print("   🗑  Cache do engine invalidado.")
    except Exception as e:
        print(f"   ⚠  Cache não invalidado: {e}")
