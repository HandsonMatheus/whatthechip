#!/usr/bin/env python
"""
db_fingerprint.py — LOCAL-ONLY, READ-ONLY (não grava NADA no banco).

Tira a "impressão digital" do banco apontado por DATABASE_URL: o conjunto de
famílias (prefixos) e de known_parts (por part_number_norm), com a marca de cada.
Rode contra o LOCALHOST e contra o PROD, depois use --diff para ver EXATAMENTE o
que cada um tem que o outro não tem (famílias e PNs), agrupado por marca.

Uso:
    # 1) snapshot do localhost (DATABASE_URL padrão do seu .env)
    python db_fingerprint.py --out local.json

    # 2) snapshot do PROD (aponte o DATABASE_URL do Render)
    DATABASE_URL="postgresql://…render.com…" python db_fingerprint.py --out prod.json

    # 3) compara os dois (não toca em banco nenhum)
    python db_fingerprint.py --diff local.json prod.json
"""
import json
import os
import sys
from collections import Counter


def snapshot(path):
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    django.setup()
    from chips.models import ChipFamily, KnownPart
    fams = sorted(ChipFamily.objects.values_list("prefix", flat=True))
    kps = {r["part_number_norm"]: [r["brand__name"], r["review_status"]]
           for r in KnownPart.objects.values("part_number_norm", "brand__name", "review_status")
           if r["part_number_norm"]}
    json.dump({"n_families": len(fams), "n_known_parts": len(kps),
               "families": fams, "known_parts": kps},
              open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ {path}: {len(fams)} famílias · {len(kps)} known_parts")


def diff(a_path, b_path):
    a = json.load(open(a_path, encoding="utf-8"))
    b = json.load(open(b_path, encoding="utf-8"))
    fa, fb = set(a["families"]), set(b["families"])
    ka, kb = set(a["known_parts"]), set(b["known_parts"])
    A, B = a_path, b_path
    print(f"\n=== {A}: {a['n_families']} famílias · {a['n_known_parts']} known_parts")
    print(f"=== {B}: {b['n_families']} famílias · {b['n_known_parts']} known_parts\n")

    print(f"── FAMÍLIAS só em {A} ({len(fa - fb)}): {sorted(fa - fb)}")
    print(f"── FAMÍLIAS só em {B} ({len(fb - fa)}): {sorted(fb - fa)}")

    only_a, only_b = ka - kb, kb - ka
    print(f"\n── known_parts SÓ em {A}: {len(only_a)}  (por marca)")
    for brand, n in Counter(a["known_parts"][k][0] for k in only_a).most_common():
        print(f"      {brand}: {n}")
    print(f"      amostra: {sorted(only_a)[:15]}")

    print(f"\n── known_parts SÓ em {B}: {len(only_b)}  (por marca)")
    for brand, n in Counter(b["known_parts"][k][0] for k in only_b).most_common():
        print(f"      {brand}: {n}")
    print(f"      amostra: {sorted(only_b)[:15]}")

    print(f"\n── em AMBOS: {len(ka & kb)} known_parts")


if __name__ == "__main__":
    if "--diff" in sys.argv:
        i = sys.argv.index("--diff")
        diff(sys.argv[i + 1], sys.argv[i + 2])
    elif "--out" in sys.argv:
        i = sys.argv.index("--out")
        snapshot(sys.argv[i + 1])
    else:
        print(__doc__)
