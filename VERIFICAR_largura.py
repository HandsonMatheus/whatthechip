"""
VERIFICAR_largura.py — a PROVA de fim de fase da separação largura x protocolo.

READ-ONLY. Nao escreve nada, em banco nenhum. Roda no banco que o DATABASE_URL
apontar (sem ele = local):

    env -u DATABASE_URL python VERIFICAR_largura.py
    env -u DATABASE_URL python VERIFICAR_largura.py --revert normalize_convention_revert_LOCAL_20260920.json
    env -u DATABASE_URL python VERIFICAR_largura.py --marca Samsung --n 25

Responde, com numeros e com PNs de verdade, as tres perguntas que o dono fez
em 2026-09-20:

  1. DE QUE E FEITO O CATALOGO? (a largura so existe em DRAM e NAND cru; se a
     conta parecer alta, e porque o catalogo E majoritariamente DRAM)
  2. DE ONDE VEIO CADA LARGURA? O backfill MOVEU valor que ja estava escrito no
     registro — nao pesquisou nem deduziu nada. Com `--revert <json>` isto vira
     PROVA registro a registro: toda largura nova tem de ser igual a que estava
     dentro da `interface` antiga.
  3. O QUE A BANCADA MOSTRA? Exemplos reais passando pelo `classify()` do
     engine, com a FONTE de cada largura separada — banco (Tier-1, o que vale),
     familia, ou gramatica (palpite de leitura, NUNCA regua).
"""
import argparse
import collections
import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection                       # noqa: E402
from chips.chip_types import spec_for                  # noqa: E402
from chips.engine import classify                      # noqa: E402
from chips.knowledge.convention import split_bus_width  # noqa: E402
from chips.models import KnownPart                     # noqa: E402

DRAM = ("dram_pc", "dram_mobile", "dram_gpu", "dram_legacy", "dram_unknown")


def balde_comercial(chip_type: str) -> str:
    """Decisao do dono (2026-09-20): a largura so vale dinheiro na DRAM de PC.

        "olha LPDDR nao me importo quase nada na vdd, o mais importante e o DDR
         e DDRL, esses sim, LPDDR e o que vem de celular e pra mim a largura
         dele n importa."

    GDDR ja estava fora do negocio desde 2026-07-23 (sempre NAO RENTAVEL).
    Entao a fila de pesquisa Tier-1 tem TRES baldes, e so um deles e trabalho.
    """
    ct = (chip_type or "").strip().upper()
    if ct.startswith("LPDDR"):
        return "LPDDR (largura nao interessa — dono 20/09)"
    if ct.startswith("GDDR"):
        return "GDDR (fora do negocio — dono 23/07)"
    return "COMERCIAL (DDR/DDR3L/DDR4/SDRAM)"


def banner():
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}\n")


def classe(ct):
    sp = spec_for((ct or "").strip())
    return sp.category if sp is not None else "(sem tipo)"


# ── 1. de que e feito o catalogo ────────────────────────────────────────────
def parte1():
    print("=" * 78)
    print("1. DE QUE E FEITO O CATALOGO  (largura so existe em DRAM e NAND cru)")
    print("=" * 78)
    por_classe = collections.Counter()
    com_larg = collections.Counter()
    for ct, bw in KnownPart.objects.values_list("chip_type", "bus_width").iterator(
            chunk_size=2000):
        c = classe(ct)
        por_classe[c] += 1
        if (bw or "").strip():
            com_larg[c] += 1
    total = sum(por_classe.values())
    print(f"{'classe':16s} {'registros':>10s} {'% catalogo':>11s} "
          f"{'com largura':>12s} {'% da classe':>12s}")
    print("-" * 78)
    for c, n in por_classe.most_common():
        cl = com_larg[c]
        print(f"{c:16s} {n:10d} {100*n/total:10.1f}% {cl:12d} "
              f"{(100*cl/n if n else 0):11.1f}%")
    print("-" * 78)
    dram = sum(n for c, n in por_classe.items() if c in DRAM)
    print(f"{'TOTAL':16s} {total:10d} {100.0:10.1f}% "
          f"{sum(com_larg.values()):12d} {100*sum(com_larg.values())/total:11.1f}%")
    print(f"\n→ DRAM (pc+mobile+gpu+legacy) = {dram} de {total} = "
          f"{100*dram/total:.1f}% do catalogo.")
    print("   A largura nao e 'metade do catalogo virou DDR': e que o catalogo")
    print("   JA E majoritariamente DRAM, e nela a largura identifica o chip.")

    # ── O BURACO: DRAM sem largura, separado pelo que VALE DINHEIRO ─────────
    print("\n   ── DRAM AINDA SEM LARGURA ──")
    falta = collections.Counter()
    for marca, ct, bw in (KnownPart.objects
                          .select_related("brand")
                          .values_list("brand__name", "chip_type", "bus_width")
                          .iterator(chunk_size=2000)):
        if classe(ct) in DRAM and not (bw or "").strip():
            falta[(balde_comercial(ct), marca or "(sem marca)", (ct or "?").strip())] += 1
    por_balde = collections.Counter()
    for (b, _m, _c), n in falta.items():
        por_balde[b] += n
    total_falta = sum(por_balde.values())
    for b, n in sorted(por_balde.items(), key=lambda kv: -kv[1]):
        print(f"   {n:6d}  {b}")
    print(f"   {total_falta:6d}  TOTAL")

    alvo = "COMERCIAL (DDR/DDR3L/DDR4/SDRAM)"
    print(f"\n   ══ FILA DE PESQUISA TIER-1 — só o balde que vale dinheiro ══")
    por_marca = collections.Counter()
    for (b, m, _c), n in falta.items():
        if b == alvo:
            por_marca[m] += n
    if not por_marca:
        print("   (nenhum) — toda a DRAM comercial já tem largura.")
        return
    print(f"   {'marca':16s} {'faltam':>7s}   por tipo")
    for marca, n in por_marca.most_common(20):
        tipos = sorted(((c, k) for (b, m, c), k in falta.items()
                        if b == alvo and m == marca), key=lambda x: -x[1])
        detalhe = " · ".join(f"{c} {k}" for c, k in tipos)
        print(f"   {marca[:16]:16s} {n:7d}   {detalhe}")
    print(f"   {'TOTAL':16s} {sum(por_marca.values()):7d}   ← este é o trabalho real")


# ── 2. de onde veio cada largura ────────────────────────────────────────────
def parte2(caminho_revert):
    print("\n" + "=" * 78)
    print("2. DE ONDE VEIO CADA LARGURA  (fonte, nao pesquisa)")
    print("=" * 78)
    # ⚠ `KnownPart` NAO tem coluna `bus_width_source` — e de proposito. O catalogo
    # guarda o VALOR; a PROCEDENCIA e resolvida em tempo de leitura pelo engine
    # (`classify()` devolve `bus_width_source`), porque ela depende de quem venceu
    # a precedencia naquela consulta: registro, familia ou gramatica. Quem tem a
    # coluna sao as entradas de LOTE, que congelam o que a tela mostrou no dia.
    # (Este script tentou ler a coluna no KnownPart em 2026-09-20 e estourou —
    # ficou o comentario para ninguem repetir.)
    larguras = collections.Counter()
    for bw in KnownPart.objects.exclude(bus_width="").values_list(
            "bus_width", flat=True).iterator(chunk_size=2000):
        larguras[bw] += 1
    print("   larguras gravadas no CATALOGO (KnownPart.bus_width):")
    for k, v in sorted(larguras.items(), key=lambda kv: -kv[1]):
        print(f"     {k:6s} {v:6d}")
    print(f"     {'TOTAL':6s} {sum(larguras.values()):6d}")
    print("\n   A procedencia (banco/familia/gramatica) e resolvida na LEITURA")
    print("   pelo engine — ver parte 3, coluna FONTE.")

    if not caminho_revert:
        print("\n   (rode com --revert <json> para a PROVA registro a registro)")
        return
    if not os.path.exists(caminho_revert):
        print(f"\n   ⚠ {caminho_revert} nao existe — prova nao feita.")
        return

    print(f"\n   PROVA contra {caminho_revert}:")
    log = json.load(open(caminho_revert))
    movidos = [e for e in log
               if e["model"] == "knownpart" and "bus_width" in e["changes"]]
    ok = divergentes = inventados = 0
    exemplos_ruins = []
    for e in movidos:
        antes_bw, depois_bw = e["changes"]["bus_width"]
        origem = (e["changes"].get("interface") or ["", ""])[0] or ""
        larg_na_interface, _, _ = split_bus_width(origem)
        if not larg_na_interface:
            inventados += 1
            exemplos_ruins.append((e["pk"], origem, depois_bw, "INVENTADA"))
        elif larg_na_interface != depois_bw:
            divergentes += 1
            exemplos_ruins.append((e["pk"], origem, depois_bw, "DIVERGENTE"))
        else:
            ok += 1
    print(f"     registros que ganharam bus_width nesta rodada: {len(movidos)}")
    print(f"     largura IGUAL a que ja estava na interface:    {ok}")
    print(f"     largura DIFERENTE da que estava na interface:  {divergentes}")
    print(f"     largura que NAO estava em lugar nenhum:        {inventados}")
    if exemplos_ruins:
        print("     ⚠ casos a olhar:")
        for pk, origem, novo, motivo in exemplos_ruins[:20]:
            print(f"        pk={pk} interface_antiga={origem!r} → bus_width={novo!r} [{motivo}]")
    else:
        print("     ✅ ZERO invencao: toda largura gravada ja estava escrita no")
        print("        proprio registro, no campo errado. O backfill MOVEU.")


# ── 3. o que a bancada mostra ───────────────────────────────────────────────
def parte3(marca_filtro, n_por_marca):
    print("\n" + "=" * 78)
    print("3. O QUE A BANCADA MOSTRA  (PNs reais pelo classify() do engine)")
    print("=" * 78)
    qs = KnownPart.objects.exclude(bus_width="").select_related("brand")
    if marca_filtro:
        qs = qs.filter(brand__name__iexact=marca_filtro)
    por_marca = collections.defaultdict(list)
    for kp in qs.order_by("brand__name", "bus_width", "part_number").iterator(
            chunk_size=2000):
        nome = kp.brand.name if kp.brand_id else "(sem marca)"
        chave = (nome, kp.bus_width)
        if len(por_marca[chave]) < n_por_marca:
            por_marca[chave].append(kp)

    print(f"{'PART NUMBER':30s} {'MARCA':14s} {'TIPO':10s} {'registro':8s} "
          f"{'TELA':8s} {'FONTE':10s}")
    print("-" * 90)
    divergiu = []
    fontes_vistas = collections.Counter()
    for (nome, larg) in sorted(por_marca):
        for kp in por_marca[(nome, larg)]:
            r = classify(kp.part_number) or {}
            tela = r.get("bus_width") or "—"
            fonte = r.get("bus_width_source") or "—"
            marca_pn = f"{kp.part_number[:30]:30s}"
            print(f"{marca_pn} {nome[:14]:14s} {(kp.chip_type or '?')[:10]:10s} "
                  f"{kp.bus_width:8s} {tela:8s} {fonte:10s}")
            fontes_vistas[fonte] += 1
            if tela != kp.bus_width:
                divergiu.append((kp.part_number, kp.bus_width, tela, fonte))
    print("-" * 90)
    print("FONTE nesta amostra: " + " · ".join(
        f"{k}={v}" for k, v in fontes_vistas.most_common()))
    print("  'banco'     = valor do registro (Tier-1/importador). E o que vale.")
    print("  'familia'   = largura fixa da familia no yaml.")
    print("  'gramatica' = leitura do PN. Palpite de bancada, NUNCA regua de preco.")
    if divergiu:
        print(f"\n⚠ {len(divergiu)} PN(s) onde a TELA mostra largura diferente do registro:")
        for pn, reg, tela, fonte in divergiu[:30]:
            print(f"   {pn:30s} registro={reg!r} tela={tela!r} fonte={fonte!r}")
        print("   (fonte='familia'/'gramatica' vencendo o registro = BUG de precedencia)")
    else:
        print("\n✅ Em todos os exemplos a tela mostra a largura DO REGISTRO.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--revert", default="", help="JSON de reversao do normalize_convention.")
    p.add_argument("--marca", default="", help="So esta marca na parte 3.")
    p.add_argument("--n", type=int, default=3, help="PNs por marca x largura (default 3).")
    a = p.parse_args()
    banner()
    parte1()
    parte2(a.revert)
    parte3(a.marca, a.n)
    print("\nNADA FOI ESCRITO.\n")
