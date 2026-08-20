# Auditoria read-only do impacto do bug de posição da RAM na família KMD
# (dossiê DOSSIE_SAMSUNG_KMD_KMDL6001DA_1.md, 2026-08-20).
#
# NÃO GRAVA NADA. Só leitura. Rode assim, apontando ao banco que quer inspecionar
# (local ou prod, com DATABASE_URL exportado):
#
#   python manage.py shell < submissions/AUDITORIA_kmd_impacto_producao_2026-08-20.py
#
# O que faz:
#   PARTE A — KnownPart (catálogo GLOBAL, todas as empresas): lista todo known_part
#     KMD, calcula a chave (pn[3:5]) e a cauda (pn[8:10]), e a RAM que a cauda prevê
#     (8M→3GB · DA/DB/DM→4GB) — sinaliza se o valor GRAVADO diverge do previsto pela
#     cauda (o known_part em si pode estar certo mesmo com a chave "errada": quem
#     manda no known_part é o dado, não a gramática — mas vale conferir).
#   PARTE B — Estoque (POR EMPRESA, itera todas as ativas): InventoryEntry e
#     PendingEntry com PN "KMD*" — mostra confidence/fonte da classificação no
#     momento do lançamento e sinaliza quando a fonte foi "gramática" (exposta ao
#     bug) e a cauda prevê valor diferente do gravado.
#
# Não decide nada sozinho — só mede. A decisão de mudar a gramática (decode_gen_pos
# 3→8 + mapa novo por cauda) é do dono, depois de ver este número.

import re
from collections import Counter

TAIL_RAM = {"8M": "3GB", "DA": "4GB", "DB": "4GB", "DM": "4GB"}


def chave(pn):
    return pn[3:5] if len(pn) >= 5 else ""


def cauda(pn):
    return pn[8:10] if len(pn) >= 10 else ""


def ram_prevista(pn):
    return TAIL_RAM.get(cauda(pn), "?")


def diverge(ram_gravado, ram_previsto):
    if ram_previsto == "?":
        return None  # cauda desconhecida, não dá pra avaliar
    return ram_previsto not in (ram_gravado or "")


print("\n" + "=" * 70)
print("PARTE A — KnownPart (catálogo GLOBAL, família KMD)")
print("=" * 70)

from chips.models import KnownPart

kmd_qs = KnownPart.objects.filter(part_number__istartswith="KMD").order_by("part_number")
total_a = kmd_qs.count()
print(f"Total known_parts KMD*: {total_a}\n")

por_confidence = Counter()
divergentes = []
for kp in kmd_qs:
    pn = kp.part_number
    ch, ca = chave(pn), cauda(pn)
    prev = ram_prevista(pn)
    div = diverge(kp.emcp_ram, prev)
    por_confidence[kp.confidence] += 1
    marca = "⚠ DIVERGE" if div else ("" if div is False else "cauda?")
    print(f"  {pn:22} chave={ch:3} cauda={ca:3} confidence={kp.confidence:12} "
          f"emcp_ram_gravado={kp.emcp_ram or '(vazio)':16} previsto_por_cauda={prev:5} {marca}")
    if div:
        divergentes.append(pn)

print(f"\nPor confidence: {dict(por_confidence)}")
print(f"known_parts KMD com RAM GRAVADA divergindo da previsão por cauda: {len(divergentes)}")
if divergentes:
    print(f"  → {divergentes}")

print("\n" + "=" * 70)
print("PARTE B — Estoque (POR EMPRESA, InventoryEntry + PendingEntry, PN KMD*)")
print("=" * 70)

from tenancy.models import Company
from tenancy.scope import company_scope
from estoque.models import InventoryEntry, PendingEntry

empresas = list(Company.objects.filter(active=True).order_by("pk"))
print(f"Empresas ativas: {[c.slug for c in empresas]}\n")

resumo_geral = Counter()
exemplos_expostos = []

for empresa in empresas:
    with company_scope(empresa):
        inv_qs = InventoryEntry.objects.filter(part_number__istartswith="KMD")
        pend_qs = PendingEntry.objects.filter(part_number__istartswith="KMD")
        n_inv, n_pend = inv_qs.count(), pend_qs.count()
        print(f"[{empresa.slug}] InventoryEntry KMD*: {n_inv}  ·  PendingEntry KMD*: {n_pend}")

        for label, qs in (("InventoryEntry", inv_qs), ("PendingEntry", pend_qs)):
            for e in qs:
                pn = e.part_number
                prev = ram_prevista(pn)
                div = diverge(e.emcp_ram, prev)
                exposta = (e.classification_source == "gramática") and bool(div)
                resumo_geral[(label, "exposta_e_divergente" if exposta else
                              "ok_ou_protegida" if div is False else
                              "protegida_por_kp" if e.classification_source == "banco de dados" else
                              "cauda_desconhecida")] += 1
                if exposta and len(exemplos_expostos) < 30:
                    exemplos_expostos.append(
                        (empresa.slug, label, pn, e.classification_source, e.emcp_ram, prev))

print(f"\nResumo geral (empresa somada): {dict(resumo_geral)}")
print(f"\nExemplos EXPOSTOS (classification_source='gramática' E cauda prevê valor "
      f"diferente do gravado — candidatos a estarem com a RAM errada HOJE):")
for slug, label, pn, src, ram_grav, prev in exemplos_expostos:
    print(f"  [{slug}] {label:16} {pn:22} fonte={src:14} gravado={ram_grav or '(vazio)':10} previsto={prev}")
if not exemplos_expostos:
    print("  (nenhum — ou o estoque não tem PN KMD* classificado por gramática com cauda "
          "divergente, ou os known_parts confirmados já cobrem tudo que está no estoque)")

print("\n" + "=" * 70)
print("FIM — nada foi gravado. Leve este resultado de volta ao chat pra decidir o fix.")
print("=" * 70)
