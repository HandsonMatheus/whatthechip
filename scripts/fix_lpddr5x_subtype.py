"""
fix_lpddr5x_subtype.py — Corrige registros LPDDR5X classificados como LPDDR5
=============================================================================
Os 25 base PNs do arquivo lpddr5x_full-catalog.csv têm TECHNOLOGY="LPDDR5"
no CSV da Micron. Se foram importados antes do fix de filename-override no
import_micron_catalog.py, podem estar com subtype="LPDDR5" em vez de "LPDDR5X".

Identificador: base PNs MT62F* que constam na lista oficial do CSV lpddr5x.

Uso:
    python scripts/fix_lpddr5x_subtype.py
    python scripts/fix_lpddr5x_subtype.py --dry-run
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

# Base PNs confirmados como LPDDR5X pelo arquivo lpddr5x_full-catalog.csv
LPDDR5X_BASES = {
    "MT62F1536M32D4DS", "MT62F1536M64D8CL", "MT62F1536M64D8CZ", "MT62F1536M64D8EK",
    "MT62F1G16D1DS",    "MT62F1G32D2DS",    "MT62F1G64D4CZ",    "MT62F1G64D4EK",
    "MT62F1G64D4ZV",    "MT62F1G64D4ZX",    "MT62F2G32D4DS",    "MT62F2G64D8CZ",
    "MT62F2G64D8DL",    "MT62F2G64D8EK",    "MT62F2G64D8ZA",    "MT62F3G32D8DV",
    "MT62F4G32D8DV",    "MT62F512M32D1DS",  "MT62F512M64D2CZ",  "MT62F512M64D2EK",
    "MT62F512M64D2ZX",  "MT62F768M32D2DS",  "MT62F768M64D4CZ",  "MT62F768M64D4EK",
    "MT62F768M64D4ZU",
}

import re
_BASE_PN_RE = re.compile(r'^(MT[A-Z0-9]+)-')

def extract_base(pn):
    m = _BASE_PN_RE.match(pn)
    return m.group(1) if m else pn.split()[0]

# Registros com prefixo MT62F que estão classificados como LPDDR5 (errado)
wrong = KnownPart.objects.filter(
    brand__name="Micron",
    chip_type="RAM",
    subtype="LPDDR5",
    part_number__startswith="MT62F",
)

to_fix = [kp for kp in wrong if extract_base(kp.part_number) in LPDDR5X_BASES]

print(f"Registros MT62F com subtype=LPDDR5 (incorreto): {wrong.count()}")
print(f"Destes, confirmados LPDDR5X pelo CSV:           {len(to_fix)}\n")

if not to_fix:
    print("✅ Nenhum registro a corrigir — subtypes já estão corretos.")
else:
    print(f"  {'PN':<50}  {'atual':>8}  {'novo':>8}")
    print(f"  {'-'*50}  {'-'*8}  {'-'*8}")
    for kp in to_fix:
        print(f"  {kp.part_number:<50}  LPDDR5  →  LPDDR5X")
        if not dry:
            kp.subtype = "LPDDR5X"
            kp.save(update_fields=["subtype", "last_updated"])

    print()
    if dry:
        print(f"⚠  DRY RUN — {len(to_fix)} seriam corrigidos.")
    else:
        print(f"✅ {len(to_fix)} registros corrigidos.")
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            print("   🗑  Cache do engine invalidado.")
        except Exception as e:
            print(f"   ⚠  Cache não invalidado: {e}")
