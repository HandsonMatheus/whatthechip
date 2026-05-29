#!/usr/bin/env python
"""
Fase 0 — Script de testes
==========================
Roda os dois comandos de deploy e verifica o estado do banco.

Uso:
    cd /caminho/para/chipdocs
    python scripts/test_fase0.py

Pré-requisito: venv ativo (ou usar: venv/bin/python scripts/test_fase0.py)
"""

import os
import sys
import django

# Bootstrap Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import ChipFamily, KnownPart, Brand

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f"  [{detail}]" if detail else ""))
        errors.append(label)

print()
print("=" * 60)
print("  FASE 0 — Deploy MT53B + smoke test")
print("=" * 60)

# ── 1. Brand Micron existe ──────────────────────────────────────
print("\n[1] Brand Micron")
micron = Brand.objects.filter(name="Micron").first()
check("Brand 'Micron' existe no banco", micron is not None)

# ── 2. Famílias Micron ──────────────────────────────────────────
print("\n[2] ChipFamilies Micron")
fam_mt53b = ChipFamily.objects.filter(prefix="MT53B").first()
fam_mt53e = ChipFamily.objects.filter(prefix="MT53E").first()
fam_mt53d = ChipFamily.objects.filter(prefix="MT53D").first()

check("MT53B (LPDDR4) existe",    fam_mt53b is not None)
check("MT53E (LPDDR4X) existe",   fam_mt53e is not None)
check("MT53D (LPDDR4) existe",    fam_mt53d is not None)

if fam_mt53b:
    check("MT53B chip_type == 'RAM'",        fam_mt53b.chip_type == "RAM",
          f"got: {fam_mt53b.chip_type}")
    check("MT53B interface == 'LPDDR4'",     fam_mt53b.interface == "LPDDR4",
          f"got: {fam_mt53b.interface}")
    check("MT53B subtype contém 'LPDDR4'",   "LPDDR4" in (fam_mt53b.subtype or ""),
          f"got: {fam_mt53b.subtype}")
    check("MT53B está ativa",                fam_mt53b.active,
          f"got: {fam_mt53b.active}")

# ── 3. KnownPart MT53B512M64D4TX ──────────────────────────────
print("\n[3] KnownPart MT53B512M64D4TX")
kp = KnownPart.objects.filter(part_number="MT53B512M64D4TX").first()

check("KnownPart MT53B512M64D4TX existe",  kp is not None)
if kp:
    check("status == 'enriched'",          kp.status == "enriched",    f"got: {kp.status}")
    check("confidence == 'confirmed'",     kp.confidence == "confirmed", f"got: {kp.confidence}")
    check("capacity == '4GB'",             kp.capacity == "4GB",       f"got: {kp.capacity}")
    check("interface == 'LPDDR4'",         kp.interface == "LPDDR4",   f"got: {kp.interface}")
    check("brand == Micron",               kp.brand.name == "Micron",  f"got: {kp.brand.name}")

# ── 4. Engine smoke test ────────────────────────────────────────
print("\n[4] Engine classify")
from chips.engine import classify

r = classify("MT53B512M64D4TX")
check("classify retorna known=True",         r.get("known") is True,        f"got: {r.get('known')}")
check("chip_type == 'RAM'",                  r.get("chip_type") == "RAM",   f"got: {r.get('chip_type')}")
check("brand == 'Micron'",                   r.get("brand") == "Micron",    f"got: {r.get('brand')}")
check("capacity ou dram_density preenchido", bool(r.get("capacity") or r.get("dram_density")),
      f"cap={r.get('capacity')} density={r.get('dram_density')}")

# Variante com sufixo de velocidade (como chega na esteira)
r2 = classify("MT53B512M64D4TX-053 WT:C")
check("classify com sufixo '-053 WT:C' retorna known=True", r2.get("known") is True,
      f"pn normalizado para: {r2.get('pn')}")
# ⚠ Esperado: o PN normalizado vira MT53B512M64D4TX053WTC (NÃO coincide com o base)
# Isso é um known limitation — resolvido na Fase 1 com fbga_code lookup.
if not r2.get("known_exact"):
    print(f"  {INFO}  PN com sufixo não tem exact match — esperado até Fase 1 (FBGA lookup)")

# ── 5. Contagem total de famílias Micron ─────────────────────────
print("\n[5] Resumo Micron")
total_fams = ChipFamily.objects.filter(brand__name="Micron").count()
total_kp   = KnownPart.objects.filter(brand__name="Micron").count()
print(f"  {INFO}  Total famílias Micron: {total_fams}")
print(f"  {INFO}  Total KnownParts Micron: {total_kp}")

# ── Resultado final ─────────────────────────────────────────────
print()
print("=" * 60)
if errors:
    print(f"  RESULTADO: {len(errors)} FALHA(S)")
    print()
    print("  Para corrigir, execute:")
    print("    python manage.py add_chip_families --overwrite")
    print("    python manage.py fix_known_parts")
    print()
    for e in errors:
        print(f"    - {e}")
else:
    print("  RESULTADO: TODOS OS TESTES PASSARAM ✅")
    print()
    print("  Fase 0 concluída. Pode avançar para a Fase 1.")
print("=" * 60)
print()
