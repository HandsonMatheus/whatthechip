"""
fix_micron_mcp_capacity.py — Corrige capacity errada em eMCP/uMCP Micron
========================================================================
Problema: ao importar os CSVs Micron (emmc-based-mcp, ufs-based-mcp), a
função _density_to_capacity() trata COMPONENT DENSITY como densidade DRAM
e converte 544Gb → 68GB (errado). O correto é:
  • MT29VZZZAD8GQFSL: NAND=64GB (512Gb) + RAM=4GB (32Gb) → capacidade NAND=64GB
  • total 544Gb é a densidade total do package, não de um componente DRAM.

Este script:
  1. Encontra todos os KnownParts Micron com prefixo MT29VZZZ* ou MT30AZZZ*
  2. Decodifica a capacidade real pelo mapa MIC_MCP_CAP (pos 8-10, 3 chars)
  3. Corrige os campos:
       capacity  → NAND capacity (valor comercialmente relevante para triagem)
       emcp_nand → versão NAND + capacidade (ex: "eMMC 5.1 64GB")
       emcp_ram  → tipo RAM + capacidade    (ex: "LPDDR4 4GB")
  4. Invalida o cache do engine

Uso:
    python scripts/fix_micron_mcp_capacity.py
    python scripts/fix_micron_mcp_capacity.py --dry-run
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

# ── Mapa de capacidade Micron MCP (idêntico ao MIC_MCP_CAP no banco) ─────────
# val_primary=NAND, val_secondary=RAM — convenção do engine
MIC_MCP_CAP = {
    "7D8": ("64GB",  "3GB"),    # 7→3GB + D8→64GB = 536Gb ✓
    "AD8": ("64GB",  "4GB"),    # A→4GB + D8→64GB = 544Gb ✓
    "BD8": ("64GB",  "6GB"),    # B→6GB + D8→64GB = 560Gb ✓
    "AD9": ("128GB", "4GB"),    # A→4GB + D9→128GB = 1056Gb ✓
    "BD9": ("128GB", "6GB"),    # B→6GB + D9→128GB = 1072Gb ✓
    "CD9": ("128GB", "8GB"),    # C→8GB + D9→128GB = 1088Gb ✓
    "BDA": ("256GB", "6GB"),    # B→6GB + DA→256GB = 2096Gb ✓
    "CDA": ("256GB", "8GB"),    # C→8GB + DA→256GB = 2112Gb ✓
    "DDA": ("256GB", "12GB"),   # D→12GB + DA→256GB = 2144Gb ✓
    "EDA": ("256GB", "16GB"),   # E→16GB + DA→256GB = 2176Gb ✓
    "CDB": ("512GB", "8GB"),    # C→8GB + DB→512GB = 4160Gb ✓
    "DDB": ("512GB", "12GB"),   # D→12GB + DB→512GB = 4192Gb ✓
    "EDB": ("512GB", "16GB"),   # E→16GB + DB→512GB = 4224Gb ✓
}

# Interface NAND por família
FAMILY_INTERFACE = {
    "MT29VZZZ": "eMMC 5.1",
    "MT30AZZZ": "UFS 3.1",
}
FAMILY_RAM_TYPE = {
    "MT29VZZZ": "LPDDR4",
    "MT30AZZZ": "LPDDR5",
}

# ── Encontrar todos os KnownParts MT29VZZZ* e MT30AZZZ* ──────────────────────
qs = KnownPart.objects.filter(
    brand__name="Micron",
    chip_type__in=["eMCP", "uMCP"],
).filter(
    part_number__startswith="MT29VZZZ"
) | KnownPart.objects.filter(
    brand__name="Micron",
    chip_type__in=["eMCP", "uMCP"],
).filter(
    part_number__startswith="MT30AZZZ"
)

qs = qs.order_by("part_number")
print(f"KnownParts MT29VZZZ* e MT30AZZZ* encontrados: {qs.count()}\n")

print(f"  {'PN':<42} {'família':<10} {'key':<5} {'NAND':<8} {'RAM':<6} {'status':>8}")
print(f"  {'-'*42} {'-'*10} {'-'*5} {'-'*8} {'-'*6} {'-'*8}")

updated = skipped = errors = 0

for kp in qs:
    pn = kp.part_number

    # Detectar família
    if pn.startswith("MT29VZZZ"):
        family_key = "MT29VZZZ"
    elif pn.startswith("MT30AZZZ"):
        family_key = "MT30AZZZ"
    else:
        print(f"  ⚠  Família desconhecida para PN: {pn}")
        errors += 1
        continue

    # Extrair chave de 3 chars em pn[8:11]
    if len(pn) < 11:
        print(f"  ⚠  PN curto demais (len={len(pn)}): {pn}")
        errors += 1
        continue

    key = pn[8:11]
    entry = MIC_MCP_CAP.get(key)

    if not entry:
        print(f"  ⚠  Chave '{key}' não mapeada — adicionar a MIC_MCP_CAP: {pn}")
        errors += 1
        continue

    nand_cap, ram_cap = entry
    nand_version = FAMILY_INTERFACE[family_key]
    ram_type     = FAMILY_RAM_TYPE[family_key]

    new_capacity   = nand_cap
    new_emcp_nand  = f"{nand_version} {nand_cap}"
    new_emcp_ram   = f"{ram_type} {ram_cap}"

    already_ok = (
        kp.capacity   == new_capacity  and
        kp.emcp_nand  == new_emcp_nand and
        kp.emcp_ram   == new_emcp_ram
    )

    status = "OK" if already_ok else ("DRY" if dry else "UPDATE")
    print(f"  {pn:<42} {family_key:<10} {key:<5} {nand_cap:<8} {ram_cap:<6} {status:>8}")

    if already_ok:
        skipped += 1
        continue

    if not dry:
        kp.capacity  = new_capacity
        kp.emcp_nand = new_emcp_nand
        kp.emcp_ram  = new_emcp_ram
        kp.save(update_fields=["capacity", "emcp_nand", "emcp_ram", "last_updated"])

    updated += 1

print()
if dry:
    print(f"⚠  DRY RUN — {updated} seriam corrigidos, {skipped} já corretos, {errors} erros.")
else:
    print(f"✅ {updated} registros corrigidos, {skipped} já corretos, {errors} erros.")
    if updated > 0:
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
            print("   🗑  Cache do engine invalidado.")
        except Exception as e:
            print(f"   ⚠  Cache não invalidado: {e}")
