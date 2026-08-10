#!/usr/bin/env python
"""
precheck_submissions.py — LOCAL-ONLY, READ-ONLY (não grava nada).

Compara os arquivos submissions/*.yaml com o banco apontado por DATABASE_URL.
RODE APONTANDO PRO PROD para descobrir, sem depender de memória, o que já está
sincronizado vs o que falta submeter/aprovar.

Uso:
    export DATABASE_URL="postgresql://…render.com…"   # o do PROD (é segredo)
    python precheck_submissions.py

Saída: por PN, o estado em prod —
    ✅ approved            → já sincronizado, nada a fazer
    🕓 submitted/draft…    → existe mas NÃO está live: só aprovar no admin
    ⬆  ausente             → submeter (submit_known_parts) + aprovar
"""
import glob
import os

import django
import yaml

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import KnownPart          # noqa: E402
from chips.normalize import normalize_pn    # noqa: E402

per_file, all_norms = {}, set()
for f in sorted(glob.glob("submissions/*.yaml")):
    try:
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
    except Exception as e:
        print(f"⚠ erro lendo {f}: {e}")
        continue
    rows = [(kp["part_number"], normalize_pn(kp["part_number"]))
            for kp in (doc.get("known_parts") or []) if kp.get("part_number")]
    if rows:
        per_file[f] = (doc.get("brand", "?"), rows)
        all_norms.update(n for _, n in rows)

status = {r["part_number_norm"]: r["review_status"]
          for r in KnownPart.objects.filter(part_number_norm__in=all_norms)
                                    .values("part_number_norm", "review_status")}

appr = sub = miss = 0
pend_files, pend_brands = [], {}
for f, (brand, rows) in sorted(per_file.items()):
    a = s = m = 0
    for pn, norm in rows:
        st = status.get(norm)
        if st == "approved":
            a += 1
        elif st:
            s += 1
        else:
            m += 1
    appr += a; sub += s; miss += m
    if s or m:
        pend_files.append((f, brand, a, s, m))
        pend_brands[brand] = pend_brands.get(brand, 0) + s + m

print(f"\n=== ESCOPO: {len(per_file)} arquivos · {len(all_norms)} PNs únicos ===")
print(f"  ✅ já APROVADOS em prod (sincronizados):            {appr}")
print(f"  🕓 submitted/não-aprovados (só APROVAR no admin):   {sub}")
print(f"  ⬆  AUSENTES em prod (SUBMETER + aprovar):           {miss}")

print(f"\n=== {len(pend_files)} ARQUIVO(S) COM PENDÊNCIA (submeter estes) ===")
for f, brand, a, s, m in pend_files:
    print(f"  [{brand:16}] {os.path.basename(f):48} aprov:{a} sub:{s} ausente:{m}")

print("\n=== marcas com pendência (nº de PNs) — pra saber onde focar: ===")
for b, n in sorted(pend_brands.items(), key=lambda x: -x[1]):
    print(f"  {b}: {n}")

if not pend_files:
    print("\n✅ NADA pendente — prod está sincronizado com suas submissions locais.")
