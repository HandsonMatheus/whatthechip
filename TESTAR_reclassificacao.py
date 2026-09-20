"""
TESTAR_reclassificacao.py — RECLASSIFICA os chips que esta tarefa tocou e mostra,
chip a chip, COMO O SISTEMA OS CLASSIFICA E QUANTO PAGA HOJE.

READ-ONLY. Roda o pipeline REAL (o mesmo do `characterize_baseline`):
classify() -> assess_profitability() -> _compute_destination() ->
is_dead_by_generation() -> pricing.derive_price_key() -> cotacao do comprador.
Tudo dentro de uma transacao REVERTIDA (o classify escreve log; nada sobra).

    env -u DATABASE_URL python TESTAR_reclassificacao.py
    env -u DATABASE_URL python TESTAR_reclassificacao.py --baseline baseline_bus_width_ANTES_local.json
    env -u DATABASE_URL python TESTAR_reclassificacao.py --pns K4B1G1646C,K4A8G165WC
    env -u DATABASE_URL python TESTAR_reclassificacao.py --todos-samsung

POR QUE ELE EXISTE (2026-09-20)
-------------------------------
Ao aplicar a submissao de largura da Samsung, 80 registros PERDERAM a geracao de
RAM que estava escrita no campo `interface` ('DDR3', 'DDR3L', 'DDR4'). Nao foi o
backfill: foi a regra 3 do `apply_kp_convention`, que proibe geracao no
`interface` desde antes desta tarefa e limpou o legado ao reencostar nele no
`save()`. O dono perguntou a unica pergunta que importa: **e agora, o sistema
classifica e PRECIFICA esses chips certo?**

Este script responde com o pipeline inteiro, nao com argumento. E ele acha os
afetados sozinho, pelo pghistory — nao por uma lista que eu digitei.

⚠ O JSON de reversao da submissao guarda so o `bus_width`; ele NAO desfaz a
limpeza do `interface`. Quem tem o valor antigo e o pghistory, e e de la que
este script tira a coluna "ANTES".
"""
import argparse
import collections
import datetime
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection, transaction                       # noqa: E402
from chips.models import KnownPart                                  # noqa: E402
from chips.management.commands.characterize_baseline import (       # noqa: E402
    _characterize_one, _contextos_de_preco)

RAM_GEN = ("DDR", "SDRAM", "LPDDR", "GDDR")
MOEDA = ("price_key", "profitable", "is_dead", "dest_label", "dest_category")


class _Rollback(Exception):
    pass


def parece_geracao(v: str) -> bool:
    t = (v or "").strip().upper()
    return bool(t) and any(t.startswith(p) for p in RAM_GEN) and "@" not in t


def afetados_pelo_pghistory(desde, candidatos=None):
    """PNs cujo `interface` PERDEU uma geracao de RAM — lido dos eventos, nao de
    uma lista minha. Devolve {pn: (antes, depois)}.

    ⚠ A 1a versao (2026-09-20) filtrava os eventos por `pgh_created_at >= hoje` e
    achou ZERO. O bug: o snapshot ANTERIOR — o que ainda tinha 'DDR3' no
    `interface` — foi gravado meses atras e ficava FORA da janela. Sem ele nao ha
    "antes" para comparar, e todo registro parecia o primeiro. O detector dizia
    "nada mudou" quando nao tinha como ver mudanca nenhuma: falha silenciosa, nao
    erro. Agora le o HISTORICO COMPLETO dos candidatos (poucos PNs, poucos
    eventos cada) e compara snapshots consecutivos. `desde` fica so como piso
    opcional para a DATA DA MUDANCA, nunca para a leitura do passado.
    """
    achados = {}
    try:
        # ⚠ O modelo de evento e `chips.KnownPartEvent` (gerado pelo
        # @pghistory.track na migration 0016) — NAO `KnownPart.events.model`:
        # `events` e um descritor reverso e nao expoe `.model`. O padrao da casa
        # esta em chips/tests.py:1567 — `apps.get_model`.
        from django.apps import apps
        Ev = apps.get_model("chips", "KnownPartEvent")
        qs = Ev.objects.order_by("pgh_obj_id", "pgh_created_at")
        if candidatos:
            # pelos PNs candidatos, HISTORICO INTEIRO (sem filtro de data)
            from chips.normalize import normalize_pn
            norm = {normalize_pn(p) for p in candidatos}
            pks = list(KnownPart.objects.filter(part_number_norm__in=norm)
                       .values_list("pk", flat=True))
            qs = qs.filter(pgh_obj_id__in=pks)
        eventos = list(qs.values("pgh_obj_id", "pgh_created_at", "part_number",
                                 "interface"))
        print(f"  pghistory: {len(eventos)} evento(s) no histórico COMPLETO de "
              f"{len(candidatos) if candidatos else 'todos os'} PN(s)")
    except Exception as exc:                                     # noqa: BLE001
        print(f"  ⚠ pghistory indisponivel ({type(exc).__name__}: {exc}).")
        print("     Em SQLite os gatilhos nao existem. Rode contra o Postgres.")
        return {}
    anterior, quando = {}, {}
    for e in eventos:
        pk = e["pgh_obj_id"]
        ant = anterior.get(pk)
        if ant is not None and parece_geracao(ant) and not (e["interface"] or "").strip():
            achados[e["part_number"]] = (ant, "")
            quando[e["part_number"]] = e["pgh_created_at"]
        anterior[pk] = e["interface"]
    if achados:
        print(f"  ⚠ {len(achados)} PN(s) perderam geração no `interface`. "
              f"Exemplos, com o valor ANTIGO e a data:")
        for pn in sorted(achados)[:10]:
            print(f"       {pn[:28]:28s} {achados[pn][0]!r} → ''   "
                  f"({quando[pn]:%Y-%m-%d %H:%M})")
    return achados


def pns_da_submissao():
    import glob
    import re
    rx = re.compile(r'^\s*-\s*part_number:\s*"?([^"\n]+?)"?\s*$')
    out = set()
    for c in sorted(glob.glob("submissions/*largura_decodificador*.yaml")):
        with open(c, encoding="utf-8") as f:
            out |= {m.group(1) for m in (rx.match(l) for l in f) if m}
    return out


def modo_chaves(a):
    """MAPA DE CHAVES DE PRECO por (chip_type, subtype).

    Nasceu em 2026-09-20 de um achado lateral: 31 Samsung sao
    `chip_type=DDR3 / subtype=DDR3L` e OUTROS 31 sao `chip_type=DDR3L`. Duas
    grafias para a mesma coisa no catalogo — e a chave de preco sai do
    chip_type. Se uma das grafias nao tem linha na tabela do comprador, aquele
    chip vale ZERO na tela e ninguem percebe: o `price_key` existe, o que falta
    e a LINHA. Este modo poe as duas coisas lado a lado.

    Dividas antigas, nao desta tarefa — mas sao as que custam em silencio.
    """
    from django.apps import apps            # noqa: F401  (simetria com o resto)
    import contextlib
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO (somente leitura) → name={d.get('NAME')}\n")

    qs = KnownPart.objects.exclude(chip_type="")
    if not a.todas_marcas:
        qs = qs.filter(brand__name__iexact=a.marca)
    pns = list(qs.values_list("part_number", flat=True))
    print(f"{len(pns)} PN(s) — marca: {'TODAS' if a.todas_marcas else a.marca}\n")

    class _Saida:
        def write(self, t):
            print(f"  {t}")

    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            ctxs, escopo = _contextos_de_preco(_Saida())
            ctxs = ctxs or []
            slug = ctxs[0][0] if ctxs else ""
            grupos = collections.Counter()
            with (escopo() if escopo else contextlib.nullcontext()):
                for pn in pns:
                    r = _characterize_one(pn, ctxs)
                    cot = str(r.get(f"price_{slug}") or "").split("|")[0] or "—"
                    grupos[(r["chip_type"], r["subtype"], r["price_key"] or "(sem chave)",
                            cot)] += 1

            if not a.so_orfas:
                print(f"{'chip_type':12s} {'subtype':12s} {'n':>5s}  "
                      f"{'CHAVE DE PREÇO':24s} COTAÇÃO")
                print("-" * 78)
            orfas = []
            for (ct, st, key, cot), n in sorted(grupos.items(),
                                                key=lambda kv: (-kv[1], kv[0])):
                aviso = ""
                if key != "(sem chave)" and cot in ("NO_ROW", "—"):
                    aviso = "  ⚠ CHAVE SEM LINHA NA TABELA"
                    orfas.append((ct, st, key, n))
                if not a.so_orfas:
                    print(f"{ct[:12]:12s} {(st or '—')[:12]:12s} {n:5d}  "
                          f"{key[:24]:24s} {cot}{aviso}")

            print("\n" + "=" * 78)
            if orfas:
                tot = sum(n for *_x, n in orfas)
                print(f"⚠ {len(orfas)} combinação(ões) com chave de preço e SEM linha na "
                      f"tabela do comprador — {tot} chip(s):")
                # Separa o que o dono JA tirou do mercado do que ainda vende —
                # sem isso a lista parece um incendio e e quase toda arquivologia.
                VELHAS = ("DDR1", "DDR2", "LPDDR1", "LPDDR2", "SDRAM")
                antigas = [o for o in orfas if o[0].upper() in VELHAS]
                vivas = [o for o in orfas if o[0].upper() not in VELHAS]
                if vivas:
                    print(f"\n  ── GERAÇÕES QUE VOCÊ VENDE ({sum(n for *_x, n in vivas)} "
                          "chips) — estes merecem olho:")
                    for ct, st, key, n in sorted(vivas, key=lambda x: -x[3]):
                        print(f"     {n:5d}  {ct}/{st or '—'}  →  {key}")
                if antigas:
                    print(f"\n  ── geração fora do mercado ({sum(n for *_x, n in antigas)} "
                          "chips) — esperado:")
                    for ct, st, key, n in sorted(antigas, key=lambda x: -x[3]):
                        print(f"     {n:5d}  {ct}/{st or '—'}  →  {key}")
                print("\n  Isso NÃO é bug desta tarefa: a chave existe, o que falta é a")
                print("  LINHA de preço. Pode ser tipo fora do mercado (DDR2, decisão")
                print("  antiga) ou uma grafia órfã que devia estar precificada.")
            else:
                print("✅ Toda chave de preço gerada tem linha na tabela do comprador.")
            raise _Rollback
    except _Rollback:
        transaction.savepoint_rollback(sid)
    print("\nNADA FOI ESCRITO (transação revertida).\n")


def main(a):
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO (somente leitura) → name={d.get('NAME')}  "
          f"host={d.get('HOST') or 'localhost'}\n")

    base = {}
    if a.baseline and os.path.exists(a.baseline):
        base = json.load(open(a.baseline))
        base = base.get("pns", base)
        print(f"baseline: {a.baseline} ({len(base)} PNs)")

    if a.pns:
        alvo, perdeu = [p.strip() for p in a.pns.split(",") if p.strip()], {}
    elif a.todos_samsung:
        alvo = list(KnownPart.objects.filter(brand__name__iexact="Samsung")
                    .values_list("part_number", flat=True))
        perdeu = {}
    else:
        submetidos = pns_da_submissao()
        perdeu = afetados_pelo_pghistory(a.desde, candidatos=submetidos)
        alvo = sorted(set(perdeu) | submetidos)
        print(f"  {len(perdeu)} PN(s) que PERDERAM geração no `interface` (pghistory)")
        print(f"  {len(alvo)} PN(s) no total a reclassificar "
              "(os que perderam + os 168 da submissão)\n")

    if not alvo:
        print("Nenhum PN a testar.\n")
        return

    class _Saida:
        def write(self, t):
            print(f"  {t}")

    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            # ⚠ Devolve uma TUPLA (contextos, platform_scope) — e o escopo NAO e
            # decorativo: comprador/lista/preco sao linhas de PLATAFORMA sob RLS,
            # e fora de request o banco devolve ZERO linhas EM SILENCIO sem o GUC.
            # Precificar sem ele daria "nenhum preco mudou" medido sobre nada —
            # exatamente a falha que este script existe para nao cometer.
            ctxs, escopo = _contextos_de_preco(_Saida())
            ctxs = ctxs or []
            nomes_preco = [f"price_{s}" for s, _ in ctxs]
            print(f"compradores ativos: {', '.join(s for s, _ in ctxs) or '(nenhum)'}")
            if not ctxs:
                print("  ⚠ SEM COTACAO. A `price_key` ainda e comparada (e o "
                      "invariante), mas o preco em RMB nao sera verificado.")
            print()

            import contextlib
            linhas, divergentes, sem_preco = [], [], []
            with (escopo() if escopo else contextlib.nullcontext()):
                for pn in alvo:
                    agora = _characterize_one(pn, ctxs)
                    antes = base.get(pn)
                    mud = [c for c in MOEDA if antes is not None
                           and (antes.get(c) or "") != (agora.get(c) or "")]
                    for np_ in nomes_preco:
                        if antes is not None and (antes.get(np_) or "") != (agora.get(np_) or ""):
                            mud.append(np_)
                    linhas.append((pn, agora, antes, mud, perdeu.get(pn)))
                    if mud:
                        divergentes.append((pn, agora, antes, mud))
                    if not (agora.get("price_key") or ""):
                        sem_preco.append((pn, agora))

            cab = (f"{'PART NUMBER':26s} {'TIPO':8s} {'SUB':8s} {'CAP':8s} "
                   f"{'LARG':5s} {'RENTAB':14s} {'CAIXA':9s} {'CHAVE DE PREÇO':26s} PREÇO")
            print(cab); print("-" * len(cab))
            for pn, agora, antes, mud, perda in linhas[:a.n]:
                preco = " · ".join(str(agora.get(n) or "—") for n in nomes_preco) or "—"
                flag = "⚠" if mud else " "
                marca = " ←perdeu geração" if perda else ""
                print(f"{flag}{pn[:25]:25s} {(agora['chip_type'] or '—')[:8]:8s} "
                      f"{(agora['subtype'] or '—')[:8]:8s} {(agora['capacity'] or '—')[:8]:8s} "
                      f"{(agora['bus_width'] or '—')[:5]:5s} {agora['profitable'][:14]:14s} "
                      f"{(agora['dest_label'] or '—')[:9]:9s} "
                      f"{(agora['price_key'] or '(sem chave)')[:26]:26s} {preco}{marca}")
            if len(linhas) > a.n:
                print(f"  … +{len(linhas) - a.n} (use --n 0 para todos)")

            print("\n" + "=" * 78)
            print(f"RECLASSIFICADOS: {len(linhas)}")
            if base:
                print(f"DIVERGEM do baseline nas colunas de DINHEIRO: {len(divergentes)}")
                if divergentes:
                    print("  ⚠ ESTES SÃO O PROBLEMA — o resto é ruído:")
                    for pn, agora, antes, mud in divergentes[:40]:
                        for c in mud:
                            print(f"     {pn[:26]:26s} {c:18s} "
                                  f"{antes.get(c)!r} → {agora.get(c)!r}")
                else:
                    print("  ✅ NENHUM. Destino, rentabilidade, chave de preço e a")
                    print("     COTAÇÃO do comprador estão iguais ao baseline de antes.")
            else:
                print("(sem baseline — rode com --baseline para comparar com o ANTES)")

            porgen = collections.Counter(
                (a_["chip_type"] or "?") for _p, a_, _b, _m, perda in linhas if perda)
            if porgen:
                print(f"\nOs {sum(porgen.values())} que perderam a geração do `interface` "
                      f"hoje classificam como: {dict(porgen.most_common())}")
                orfaos = [p for p, a_, _b, _m, perda in linhas
                          if perda and not (a_["chip_type"] or "").strip()]
                if orfaos:
                    print(f"  ⚠⚠ {len(orfaos)} FICARAM SEM chip_type — a geração morava "
                          f"SÓ no interface: {orfaos[:20]}")
                else:
                    print("  ✅ TODOS têm `chip_type` preenchido.")

                # ⚠ "tem chip_type" NAO e o mesmo que "diz a MESMA coisa". Achado
                # em 2026-09-20: 31 registros cujo `interface` dizia 'DDR3L' tem
                # `chip_type` = 'DDR3'. O "L" morava SO no campo errado, e a
                # limpeza apagou o unico vestigio de que o catalogo podia estar
                # errado. Nao mudou preco (o preco ja vinha do chip_type), mas
                # some a evidencia — entao ela vira relatorio.
                iguais, difere = 0, []
                for p, a_, _b, _m, perda in linhas:
                    if not perda:
                        continue
                    antigo = (perda[0] or "").strip().upper()
                    atual = (a_["chip_type"] or "").strip().upper()
                    if antigo == atual:
                        iguais += 1
                    else:
                        difere.append((p, perda[0], a_["chip_type"],
                                       a_["subtype"], a_["price_key"]))
                print(f"\n  cópia EXATA do chip_type (nada a decidir): {iguais}")
                if difere:
                    print(f"  ⚠ DIVERGENTES: {len(difere)} — o `interface` dizia uma "
                          "coisa e o `chip_type` diz outra.")
                    print("     Se o valor ANTIGO estiver certo, o catálogo está errado "
                          "HOJE e corrigir o `chip_type` MEXE EM PREÇO.\n")
                    print(f"     {'PART NUMBER':28s} {'interface dizia':16s} "
                          f"{'chip_type diz':14s} {'subtype':10s} chave de preço")
                    for p, antigo, ct, st, pk in difere:
                        print(f"     {p[:28]:28s} {antigo!r:16s} {ct:14s} "
                              f"{(st or '—'):10s} {pk or '(sem chave)'}")

            if sem_preco:
                print(f"\n{len(sem_preco)} sem chave de preço (pode ser normal — "
                      "capacidade indisponível, tipo fora do mercado):")
                for pn, ag in sem_preco[:15]:
                    print(f"     {pn[:26]:26s} {ag.get('price_no_key_reason','')[:60]}")
            raise _Rollback
    except _Rollback:
        transaction.savepoint_rollback(sid)
    print("\nNADA FOI ESCRITO (transação revertida).\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", default="baseline_bus_width_ANTES_local.json")
    p.add_argument("--pns", default="", help="lista separada por vírgula")
    p.add_argument("--todos-samsung", action="store_true")
    p.add_argument("--desde", default=str(datetime.date.today()),
                   help="data mínima dos eventos do pghistory (AAAA-MM-DD)")
    p.add_argument("--n", type=int, default=40, help="linhas na tabela (0 = todas)")
    p.add_argument("--chaves", action="store_true",
                   help="MAPA de chave de preço por (chip_type, subtype)")
    p.add_argument("--marca", default="Samsung")
    p.add_argument("--todas-marcas", action="store_true")
    p.add_argument("--so-orfas", action="store_true",
                   help="pula o quadro grande; só o resumo das chaves sem linha")
    a = p.parse_args()
    if a.n == 0:
        a.n = 10 ** 9
    modo_chaves(a) if a.chaves else main(a)
