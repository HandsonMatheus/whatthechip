"""Acha o UNICO PN cujo subtype gravado pelo backfill DEGRADOU a tela.

O `--diff` de 2026-09-20 mostrou, entre as 59 mudancas de `subtype` na TELA, uma
transicao que NAO existe no relatorio do comando: 'LPDDR4X' -> 'LPDDR4'. Isso so
acontece quando a tela mostrava a geracao vinda da GRAMATICA/FAMILIA (LPDDR4X) e
o backfill gravou no registro uma geracao MENOS especifica (LPDDR4, tirada do
proprio `emcp_ram`), que passa a vencer a gramatica. Nao e da excecao 3 (largura)
— e da excecao 2 (geracao, 2026-08-28) —, mas aconteceu nesta rodada.

Read-only. Roda contra o banco que o DATABASE_URL apontar.

    env -u DATABASE_URL python DIAGNOSTICAR_lpddr4x.py normalize_convention_revert_LOCAL_20260920.json
"""
import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import KnownPart          # noqa: E402

caminho = sys.argv[1] if len(sys.argv) > 1 else "normalize_convention_revert.json"
log = json.load(open(caminho))
pks = [e["pk"] for e in log
       if e["model"] == "knownpart" and "subtype" in e["changes"]]
print(f"{len(pks)} KnownPart tiveram `subtype` gravado nesta rodada.\n")

print(f"{'PART NUMBER':30s} {'antes':12s} {'gravado':10s} {'FAMILIA':10s} "
      f"{'fam.subtype':16s} emcp_ram")
print("-" * 118)
antes_por_pk = {e["pk"]: e["changes"]["subtype"][0] for e in log
                if e["model"] == "knownpart" and "subtype" in e["changes"]}
suspeitos = []
for kp in (KnownPart.objects.filter(pk__in=pks)
           .select_related("family").order_by("part_number")):
    fam = kp.family
    fam_sub = (fam.subtype or "") if fam else ""
    linha = (f"{kp.part_number[:30]:30s} {(antes_por_pk[kp.pk] or '(vazio)')[:12]:12s} "
             f"{kp.subtype[:10]:10s} {(fam.prefix if fam else '-')[:10]:10s} "
             f"{fam_sub[:16]:16s} {(kp.emcp_ram or '')[:34]!r}")
    # A tela degradou quando a familia sabia MAIS que o registro agora diz.
    if fam_sub and kp.subtype and fam_sub != kp.subtype \
            and fam_sub.upper().startswith(kp.subtype.upper()):
        suspeitos.append(linha)
        linha = "⚠ " + linha
    else:
        linha = "  " + linha
    print(linha)

print()
if suspeitos:
    print(f"⚠ {len(suspeitos)} registro(s) onde a FAMILIA era mais especifica que "
          "o valor gravado — a tela perdeu informacao:")
    for s in suspeitos:
        print("   " + s)
else:
    print("Nenhum registro ficou menos especifico que a propria familia.")
