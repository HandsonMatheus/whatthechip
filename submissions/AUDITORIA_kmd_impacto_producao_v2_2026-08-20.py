# Auditoria KMD — v2, refinada a partir do resultado da v1 (rodada real em prod,
# 2026-08-20). Achado da v1 que motiva esta v2:
#
#   4 known_parts confirmados existem mas com emcp_ram VAZIO (KMDH6001DA,
#   KMDP60018M, KMDV6001DA, KMDV6001DM). O engine (_result_from_known), quando o
#   known_part é confirmed/manual mas emcp_ram vem vazio, NÃO sobrescreve com
#   vazio — mantém o valor que a GRAMÁTICA (possivelmente errada) já tinha
#   calculado, e ainda assim rotula classification_source="banco de dados". Ou
#   seja: a v1 pode ter contado como "protegida_por_kp" um InventoryEntry que na
#   verdade está exposto ao bug, só que com um known_part vazio no meio do
#   caminho. Esta v2 cruza os 4 PNs vazios/divergentes direto contra o estoque,
#   sem depender do rótulo classification_source.
#
# Read-only. Rode:
#   python manage.py shell < submissions/AUDITORIA_kmd_impacto_producao_v2_2026-08-20.py

PNS_SUSPEITOS = ["KMDH6001DA", "KMDP60018M", "KMDV6001DA", "KMDV6001DM"]

print("\n" + "=" * 70)
print("PARTE C — classify() AGORA para os 4 PNs com known_part vazio/divergente")
print("=" * 70)
from chips.engine import classify
for pn in PNS_SUSPEITOS:
    r = classify(pn) or {}
    print(f"  {pn:14} emcp_ram={r.get('emcp_ram')!r:40} classification_source={r.get('classification_source')!r} "
          f"confidence={r.get('confidence')!r} known_exact={r.get('known_exact')}")

print("\n" + "=" * 70)
print("PARTE D — esses 4 PNs aparecem no estoque de alguma empresa?")
print("=" * 70)
from tenancy.models import Company
from tenancy.scope import company_scope
from estoque.models import InventoryEntry, PendingEntry

achados = []
for empresa in Company.objects.filter(active=True).order_by("pk"):
    with company_scope(empresa):
        for label, model in (("InventoryEntry", InventoryEntry), ("PendingEntry", PendingEntry)):
            for e in model.objects.filter(part_number__in=PNS_SUSPEITOS):
                achados.append((empresa.slug, label, e.part_number,
                                 e.classification_source, e.emcp_ram))
                print(f"  [{empresa.slug}] {label:16} {e.part_number:14} "
                      f"classification_source={e.classification_source!r} emcp_ram_snapshot={e.emcp_ram!r}")

if not achados:
    print("  (nenhum — os 4 PNs suspeitos não aparecem hoje no estoque de nenhuma empresa)")
else:
    print(f"\n  → {len(achados)} entrada(s) de estoque tocam PN com known_part vazio/divergente.")

print("\n" + "=" * 70)
print("PARTE E — tail 'BM' (achado novo na v1: KMDD6001BM/KMDX6001BM, ambos 3GB) —")
print("mais peças com essa cauda existem no catálogo?")
print("=" * 70)
from chips.models import KnownPart
for kp in KnownPart.objects.filter(part_number__istartswith="KMD").order_by("part_number"):
    if kp.part_number[8:10] == "BM":
        print(f"  {kp.part_number:14} confidence={kp.confidence:10} emcp_ram={kp.emcp_ram!r}")

print("\n" + "=" * 70)
print("FIM v2 — nada gravado.")
print("=" * 70)
