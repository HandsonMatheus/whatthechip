"""
fix_micron_db.py — Corrige inconsistências confirmadas no banco Micron
======================================================================
Fixes aplicados (todos com evidência concreta):

  1. Deleta id=4869 (MT53E1536M64D8HJ046AITB)
     — PN malformado, manual, sem FBGA. Registro correto já existe com FBGA D8BMG.

  2. Deleta id=4201 (MT29TZZZ8D5BKFAN)
     — eMCP sem FBGA, API retornou nada, aprovado pelo usuário.

  3. id=4164 subtype 'LPDDR4 standalone' → 'LPDDR4'
     — Valor inválido, chip confirmado LPDDR4 (FBGA D9VFC).

  4. MT62F2G64D8DL density_gbit '16GB' → '128Gb'
     — Inconsistência da Micron no CSV: sister part MT62F2G64D8EK = 128Gb
       para configuração idêntica (2Gb x64, 8 components).
     — capacity '16GB' mantida (correta: 128Gb ÷ 8 = 16GB).

  5. 79 registros RAM sem subtype — inferido por prefixo de PN:
     — MT62F → LPDDR5  (confirmado pelo CSV lpddr5_full-catalog.csv)
     — MT53B, MT53D, MT53E → LPDDR4  (confirmado pelo CSV lpddr4_full-catalog.csv)
     — MT401A → DDR4  (confirmado pelo CSV ddr4-sdram_full-catalog.csv)
     — Exclui id=4869 (já deletado no fix 1)

Uso:
    python scripts/fix_micron_db.py
    python scripts/fix_micron_db.py --dry-run
"""

import os, sys, django, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db.models import Q
from chips.models import KnownPart

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()
dry = args.dry_run

if dry:
    print("⚠  DRY RUN — nenhuma alteração será salva.\n")

counts = {"deleted": 0, "updated": 0, "fields": 0}

def log(msg): print(f"  {msg}")

# ── Fix 1 & 2: Deletar registros inválidos ────────────────────────────────────
print("═" * 60)
print("FIX 1+2 — Deletar registros inválidos")

TO_DELETE = [
    (4869, "MT53E1536M64D8HJ046AITB", "PN malformado, duplicata do registro com FBGA D8BMG"),
    (4201, "MT29TZZZ8D5BKFAN",        "eMCP sem FBGA, API retornou nada, aprovado para deleção"),
]

for pk, pn, motivo in TO_DELETE:
    try:
        kp = KnownPart.objects.get(id=pk)
        log(f"[DELETE] id={pk}  PN={kp.part_number}")
        log(f"         motivo: {motivo}")
        if not dry:
            kp.delete()
        counts["deleted"] += 1
    except KnownPart.DoesNotExist:
        log(f"[SKIP]   id={pk} não encontrado (já deletado?)")

# ── Fix 3: Subtype 'LPDDR4 standalone' → 'LPDDR4' ────────────────────────────
print()
print("═" * 60)
print("FIX 3 — Subtype 'LPDDR4 standalone' → 'LPDDR4'")

try:
    kp = KnownPart.objects.get(id=4164)
    log(f"[UPDATE] id=4164  PN={kp.part_number}")
    log(f"         subtype: '{kp.subtype}' → 'LPDDR4'")
    if not dry:
        kp.subtype = "LPDDR4"
        kp.save(update_fields=["subtype", "last_updated"])
    counts["updated"] += 1
    counts["fields"]  += 1
except KnownPart.DoesNotExist:
    log("[SKIP] id=4164 não encontrado")

# ── Fix 4: MT62F2G64D8DL density '16GB' → '128Gb' ────────────────────────────
print()
print("═" * 60)
print("FIX 4 — MT62F2G64D8DL density_gbit '16GB' → '128Gb'")

dl_parts = KnownPart.objects.filter(
    part_number__startswith="MT62F2G64D8DL",
    density_gbit="16GB",
)
log(f"Registros encontrados: {dl_parts.count()}")
for kp in dl_parts:
    log(f"[UPDATE] PN={kp.part_number}")
    log(f"         density_gbit: '16GB' → '128Gb'  |  capacity mantida: '{kp.capacity}'")
    if not dry:
        kp.density_gbit = "128Gb"
        kp.save(update_fields=["density_gbit", "last_updated"])
    counts["updated"] += 1
    counts["fields"]  += 1

# ── Fix 5: RAM sem subtype — inferir por prefixo ──────────────────────────────
print()
print("═" * 60)
print("FIX 5 — RAM sem subtype → inferir por prefixo do PN")

PREFIX_MAP = {
    "MT62F": "LPDDR5",
    "MT53B": "LPDDR4",
    "MT53D": "LPDDR4",
    "MT53E": "LPDDR4",
    "MT401": "DDR4",    # MT401AAD1TD
}

no_sub_ram = KnownPart.objects.filter(
    chip_type="RAM",
).filter(
    Q(subtype="") | Q(subtype__isnull=True)
).exclude(id=4869)  # já deletado

log(f"Registros RAM sem subtype: {no_sub_ram.count()}")

fixed = skipped = 0
for kp in no_sub_ram:
    pn_prefix = kp.part_number[:5]
    subtype = PREFIX_MAP.get(pn_prefix)

    if not subtype:
        log(f"[SKIP]   PN={kp.part_number}  — prefixo '{pn_prefix}' não mapeado")
        skipped += 1
        continue

    log(f"[UPDATE] PN={kp.part_number[:50]:50s}  → subtype='{subtype}'")
    if not dry:
        kp.subtype = subtype
        kp.save(update_fields=["subtype", "last_updated"])
    fixed += 1
    counts["updated"] += 1
    counts["fields"]  += 1

log(f"\nSubtypes atualizados: {fixed}  |  prefixos não mapeados: {skipped}")

# ── Relatório ─────────────────────────────────────────────────────────────────
print()
print("═" * 60)
print(f"✅  Concluído.")
print(f"   Registros deletados:   {counts['deleted']}")
print(f"   Registros atualizados: {counts['updated']}")
print(f"   Campos corrigidos:     {counts['fields']}")

if dry:
    print("\n⚠  DRY RUN — nenhuma alteração foi salva.")
else:
    # Invalida cache do engine
    try:
        from chips.engine import clear_engine_cache
        clear_engine_cache()
        print("   🗑  Cache do engine invalidado.")
    except Exception as e:
        print(f"   ⚠  Cache não invalidado: {e}")
