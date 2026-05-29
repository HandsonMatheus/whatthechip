#!/usr/bin/env python
"""
Fase 1 — Script de testes
==========================
Verifica: campo fbga_code no modelo, migration aplicada, engine FBGA.

Uso (após migrate + fix_known_parts):
    cd /caminho/para/chipdocs
    python scripts/test_fase1.py

Pré-requisito: Fase 0 passou + migration 0009 aplicada.
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import KnownPart
from chips.engine import classify, _FBGA_RE

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"
WARN = "⚠️  WARN"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f"  [{detail}]" if detail else ""))
        errors.append(label)

print()
print("=" * 60)
print("  FASE 1 — Campo fbga_code + Engine FBGA")
print("=" * 60)

# ── 1. Migration aplicada (campo existe no modelo) ─────────────
print("\n[1] Campo fbga_code no modelo")
try:
    has_field = hasattr(KnownPart, 'fbga_code') and \
                'fbga_code' in [f.name for f in KnownPart._meta.get_fields()]
    check("Campo fbga_code existe em KnownPart", has_field)
except Exception as e:
    check("Campo fbga_code existe em KnownPart", False, str(e))

# Testa que o campo aceita valor vazio (default)
try:
    kp_test = KnownPart.objects.first()
    if kp_test:
        _ = kp_test.fbga_code  # não deve lançar AttributeError
        check("Campo fbga_code acessível em instância existente", True)
    else:
        print(f"  {INFO}  Sem KnownParts no banco — skip teste de instância")
except AttributeError as e:
    check("Campo fbga_code acessível em instância existente", False, str(e))
    print(f"  {WARN}  Execute: python manage.py migrate")

# ── 2. D9VFC preenchido no MT53B512M64D4TX ─────────────────────
print("\n[2] FBGA code D9VFC cadastrado")
kp = KnownPart.objects.filter(part_number="MT53B512M64D4TX").first()
check("KnownPart MT53B512M64D4TX existe",    kp is not None)
if kp:
    check("fbga_code == 'D9VFC'",             kp.fbga_code == "D9VFC",
          f"got: '{kp.fbga_code}' — rode: python manage.py fix_known_parts")

# ── 3. Regex FBGA (_FBGA_RE) ────────────────────────────────────
print("\n[3] Regex _FBGA_RE")

fbga_positivos = ["D9VFC", "D9TBH", "D9WFJ", "D9SHD", "D8TXF", "A1BCD"]
fbga_negativos = ["MT53B", "KLMCG", "H9TQ08", "D9VFC1", "D9VF", "12345", ""]

for code in fbga_positivos:
    check(f"'{code}' reconhecido como FBGA", bool(_FBGA_RE.match(code)))

for code in fbga_negativos:
    check(f"'{code}' NÃO é FBGA (negativo)", not bool(_FBGA_RE.match(code)),
          f"'{code}' foi falso positivo!")

# ── 4. Engine: lookup por FBGA code ────────────────────────────
print("\n[4] Engine classify — FBGA lookup")

# 4a. FBGA conhecido → deve retornar o chip
r = classify("D9VFC")
check("classify('D9VFC') retorna known=True",        r.get("known") is True,
      f"got known={r.get('known')}, fbga_unknown={r.get('fbga_unknown')}")
check("resultado tem pn_full='MT53B512M64D4TX'",      r.get("pn_full") == "MT53B512M64D4TX",
      f"got pn_full='{r.get('pn_full')}', pn='{r.get('pn')}'")
check("resultado tem fbga_input='D9VFC'",             r.get("fbga_input") == "D9VFC",
      f"got: '{r.get('fbga_input')}'")
check("chip_type == 'RAM'",                           r.get("chip_type") == "RAM",
      f"got: '{r.get('chip_type')}'")
check("capacity == '4GB'",                            r.get("capacity") == "4GB",
      f"got: '{r.get('capacity')}'")
check("brand == 'Micron'",                            r.get("brand") == "Micron",
      f"got: '{r.get('brand')}'")
check("classification_source contém 'banco'",
      "banco" in str(r.get("classification_source", "")).lower(),
      f"got: '{r.get('classification_source')}'")

# 4b. FBGA desconhecido → deve retornar fbga_unknown=True
r2 = classify("D9ZZZ")
check("classify('D9ZZZ') retorna known=False",        r2.get("known") is False,
      f"got: known={r2.get('known')}")
check("classify('D9ZZZ') retorna fbga_unknown=True",  r2.get("fbga_unknown") is True,
      f"got: {r2.get('fbga_unknown')}")

# Verificar que foi para UnknownChip
from chips.models import UnknownChip
unk = UnknownChip.objects.filter(part_number="D9ZZZ").first()
check("D9ZZZ registrado em UnknownChip",              unk is not None,
      "UnknownChip não encontrado — verificar engine.py")
if unk:
    check("notes contém 'FBGA'",
          "FBGA" in (unk.notes or ""),
          f"got notes: '{unk.notes}'")

# 4c. PN normal ainda funciona (não-regressão) ─────────────────
print("\n[5] Não-regressão — PNs normais continuam funcionando")

# Samsung eMCP — deve resolver pela gramática ou banco
r3 = classify("KLM8G1GETF")
check("classify('KLM8G1GETF') retorna known=True",    r3.get("known") is True,
      f"got: {r3.get('known')}")
check("KLM8G1GETF NÃO ativou FBGA lookup",
      not r3.get("fbga_unknown") and not r3.get("fbga_input"),
      f"fbga_unknown={r3.get('fbga_unknown')}, fbga_input={r3.get('fbga_input')}")

# SK Hynix — prefixo que começa com letra+letra (não é FBGA)
r4 = classify("H9TQ08AGDTMCUR")
check("classify('H9TQ08AGDTMCUR') NÃO ativou FBGA lookup",
      not r4.get("fbga_unknown") and not r4.get("fbga_input"),
      f"fbga_unknown={r4.get('fbga_unknown')}")

# MT53B512M64D4TX pelo PN completo ainda funciona (exact match)
r5 = classify("MT53B512M64D4TX")
check("classify('MT53B512M64D4TX') ainda funciona pelo PN completo",
      r5.get("known") is True,
      f"got: {r5.get('known')}")
check("MT53B512M64D4TX NÃO ativou FBGA lookup",
      not r5.get("fbga_input"),
      f"fbga_input={r5.get('fbga_input')}")

# ── 6. Admin: fbga_code nos campos de busca ─────────────────────
print("\n[6] Admin")
try:
    from chips.admin import KnownPartAdmin
    from django.contrib.admin.sites import AdminSite
    admin_instance = KnownPartAdmin(KnownPart, AdminSite())
    check("fbga_code em list_display do admin",
          "fbga_code" in admin_instance.list_display,
          f"list_display: {admin_instance.list_display}")
    check("fbga_code em search_fields do admin",
          "fbga_code" in admin_instance.search_fields,
          f"search_fields: {admin_instance.search_fields}")
except Exception as e:
    check("Admin importa sem erro", False, str(e))

# ── Resultado final ─────────────────────────────────────────────
print()
print("=" * 60)
if errors:
    print(f"  RESULTADO: {len(errors)} FALHA(S)")
    print()
    print("  Checklist de correção:")
    print("    1. python manage.py migrate")
    print("    2. python manage.py add_chip_families --overwrite")
    print("    3. python manage.py fix_known_parts")
    print("    4. python manage.py clear_cache  (se existir)")
    for e in errors:
        print(f"    - FALHOU: {e}")
else:
    print("  RESULTADO: TODOS OS TESTES PASSARAM ✅")
    print()
    print("  Fase 1 concluída. Pode avançar para a Fase 2 (scrape_preduo.py).")
print("=" * 60)
print()

# ── Limpeza: remove D9ZZZ do UnknownChip após o teste ──────────
try:
    UnknownChip.objects.filter(part_number="D9ZZZ").delete()
    print("  (D9ZZZ removido do UnknownChip após teste)")
except Exception:
    pass
