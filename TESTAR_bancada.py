# -*- coding: utf-8 -*-
"""
TESTAR_bancada.py — READ-ONLY. "Está indo tudo pro lugar certo?"

Não é a suíte (essa é `python manage.py test estoque --settings=core.settings_test`).
Isto é a BANCADA SIMULADA: pega PN de verdade do SEU catálogo, roda o motor de
verdade e mostra, chip por chip e origem por origem, o que a bancada faria.

    python TESTAR_bancada.py                      # escolhe PNs reais, um punhado por tipo
    python TESTAR_bancada.py K4F6E3S4HM NT5CC256  # os PNs que você quiser
    python TESTAR_bancada.py --censo              # varre o catálogo INTEIRO e conta
    python TESTAR_bancada.py --censo --limite 2000

Contra produção também serve — não escreve nada, e o que ele faz ler roda dentro
de uma transação que é revertida no fim (mesmo cinto do `characterize_baseline`).

⚠ O QUE ELE **NÃO** PROVA: que a view `add_chip` grava certo. Isso é a suíte, com
banco de teste descartável. Aqui é o MOTOR + a RÉGUA, sobre o seu dado real —
que é a pergunta "os meus chips vão pro lugar certo?", não "o código funciona?".
"""
import argparse
import collections
import sys

# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('pns', nargs='*', help='PNs a testar (vazio = escolhe do catálogo)')
    ap.add_argument('--censo', action='store_true',
                    help='varre o catálogo inteiro e conta quanto cada origem barra')
    ap.add_argument('--limite', type=int, default=0,
                    help='teto de PNs no censo (0 = catálogo INTEIRO, que é o '
                         'padrão; um teto corta em ORDEM ALFABÉTICA e enviesa '
                         'a conta por marca — use só pra espiar rápido)')
    ap.add_argument('--por-tipo', type=int, default=2,
                    help='quantos PNs por tipo na amostra automática (padrão 2)')
    args = ap.parse_args()

    import os
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    import django
    django.setup()

    from django.db import connection, transaction
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}\n")

    _tabela_existe_ou_sai()

    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            if args.censo:
                ok = censo(args.limite)
            else:
                ok = matriz(args.pns, args.por_tipo)
    finally:
        transaction.savepoint_rollback(sid)
    sys.exit(0 if ok else 1)


# ─────────────────────────────────────────────────────────────────────────────

def _tabela_existe_ou_sai():
    """Pré-voo: a torneira mora numa tabela que só nasce com a migração 0024.
    Sem ela, TODA consulta da política estoura — e, no Postgres, o primeiro erro
    aborta a transação, então tudo depois vira "current transaction is aborted"
    e a saída não diz mais nada. Melhor dizer o que fazer do que despejar
    traceback.

    Sai com 2 (≠ 1): "ainda não dá pra testar" não é "testei e falhou"."""
    import sys
    from django.db import connection
    tabela = 'estoque_politicaorigemtipo'
    if tabela in connection.introspection.table_names():
        return
    print(f"⏸  A tabela da torneira ({tabela}) ainda NÃO existe neste banco.\n"
          "   Isto não é falha do código — é migração que falta. Rode:\n\n"
          "       python manage.py migrate estoque\n\n"
          "   e rode este script de novo. (Nada foi lido nem escrito.)")
    sys.exit(2)


def _origens():
    """As origens que o gerente pode abrir HOJE. As legadas (MIXED/K9) ficam de
    fora porque não há lote novo delas — testar seria testar o passado."""
    from estoque.models import Lot
    return Lot.origin_choices_novas()


def _analisar(pn):
    """Roda o motor DE VERDADE sobre um PN e devolve tudo que a bancada decide.

    ⚠ A ORDEM do funil abaixo é um ESPELHO do `estoque/views.py::add_chip`
    (fila → descarte → sem-avaliação → origem → entra). A verdade mora lá; se
    um dia a ordem mudar lá e não mudar aqui, este script passa a mentir. Quem
    trava a ordem de verdade é `PoliticaOrigemBancadaTests`
    (`test_sucata_no_lote_errado_AINDA_gera_RejectedEntry`), não este arquivo.
    """
    from chips.engine import classify
    from estoque.models import Lot
    from estoque.views import (_compute_destination, _compute_gateway,
                               _has_capacity, _price_key_fields)

    result = classify(pn)
    for k in ('chip_type', 'subtype', 'capacity', 'dram_density', 'interface',
              'brand', 'emcp_ram', 'emcp_nand', 'classification_source'):
        result.setdefault(k, '')
    has_cap = _has_capacity(result)

    chave = _price_key_fields(result)
    linha = {
        'pn':      pn,
        'tipo':    result.get('chip_type') or '—',
        'kind':    chave.get('price_kind') or '—',
        'destino': _compute_destination(result),
        'chave':   _fmt_chave(chave),
        'por_origem': {},
        'colunas_por_origem': {},
    }

    for origem, _rotulo in _origens():
        g = _compute_gateway(result, has_cap, lot=Lot(origin=origem))
        # ⚠ ESTA ORDEM É O `add_chip`, LINHA POR LINHA — e eu já errei aqui uma
        # vez (2026-09-09): tinha posto `origem` ANTES de `não lança`, e o censo
        # contou como BARRADO ~108 chips que na verdade param antes, por
        # rentabilidade não avaliada. Ordem errada num relatório não dá erro:
        # dá um número plausível e errado, que é pior.
        if   g['destination'] == 'desconhecido':      veredito = 'DESCONHECIDO'
        elif g['destination'] == 'fila':              veredito = 'FILA'
        elif g['destination'] == 'reprovado':         veredito = 'DESCARTE'
        elif g['profitable'] != 'RENTÁVEL':           veredito = 'não lança'
        elif g['origem_bloqueada']:                   veredito = 'BARRADO'
        else:                                         veredito = 'ENTRA'
        linha['por_origem'][origem] = (veredito, g['origem_bloqueada'])
        # as TRÊS COLUNAS, recalculadas com o lote em mãos — têm que ser iguais
        # às de cima em toda origem. É a prova de que a torneira não vazou.
        linha['colunas_por_origem'][origem] = (
            _compute_destination(result), g['profitable'], _fmt_chave(chave))
    linha['rentab'] = _compute_gateway(result, has_cap)['profitable'] or '—'
    return linha


def _fmt_chave(c):
    if c.get('price_key_reason'):
        return f"— ({c['price_key_reason'][:34]})"
    v = c.get('price_tier_value')
    return f"{c['price_kind']}|{c['price_gen'] or '·'}|{v}|{c['price_tier_unit']}"


# ─────────────────────────────────────────────────────────────────────────────
def _amostra(por_tipo):
    """Escolhe PNs REAIS do catálogo, alguns de cada tipo. Só aprovado e
    autoritativo (confirmed/manual) — é o que a bancada trata como verdade."""
    from chips.engine import classify
    from chips.models import KnownPart
    from estoque.views import _price_key_fields

    qs = (KnownPart.objects
          .filter(review_status='approved', confidence__in=('confirmed', 'manual'))
          .exclude(part_number='')
          .order_by('part_number')
          .values_list('part_number', flat=True))
    total = qs.count()
    if total == 0:
        print("✗ ZERO known_parts aprovados neste banco — sem catálogo não há o que\n"
              "  testar. (Se isto é produção, é alarme: veja a regra de ouro §2.1b.)")
        return [], 0

    por_kind, vistos, falhas_amostra = collections.defaultdict(list), 0, []
    for pn in qs.iterator(chunk_size=500):
        vistos += 1
        if vistos > 3000:
            break
        try:
            k = _price_key_fields(classify(pn)).get('price_kind') or 'none'
        except Exception as e:                                   # noqa: BLE001
            # Aqui o `continue` é legítimo — é ESCOLHA de amostra, não medição —
            # mas erro em massa esconderia catálogo quebrado. Conta e reporta.
            falhas_amostra.append((pn, f'{type(e).__name__}: {e}'))
            continue
        if len(por_kind[k]) < por_tipo:
            por_kind[k].append(pn)
        if len(por_kind) >= 10 and all(len(v) >= por_tipo for v in por_kind.values()):
            if vistos > 800:
                break
    if falhas_amostra:
        print(f"⚠  {len(falhas_amostra)} PN(s) não classificaram na escolha da "
              f"amostra. Primeiro: {falhas_amostra[0][0]} — {falhas_amostra[0][1]}")
        if len(falhas_amostra) > vistos // 2:
            print("✗ Mais da METADE do catálogo varrido falhou. Isto não é amostra "
                  "ruim, é catálogo ou banco quebrado — pare e olhe.")
            return [], total
    escolhidos = [pn for k in sorted(por_kind) for pn in por_kind[k]]
    return escolhidos, total


def matriz(pns, por_tipo):
    from estoque.models import Lot, PoliticaOrigemTipo

    if pns:
        total = len(pns)
        print(f"PNs informados por você: {total}\n")
    else:
        pns, total_catalogo = _amostra(por_tipo)
        if not pns:
            return False
        print(f"Amostra automática: {len(pns)} PN(s) reais, "
              f"de {total_catalogo} aprovados no catálogo\n")

    origens = _origens()
    cab_org = [str(r) for _v, r in origens]
    larg = max(12, max((len(c) for c in cab_org), default=12) + 2)

    print("═" * (34 + 10 + 13 + 24 + larg * len(origens)))
    print(f"{'PN':<22}{'TIPO':<12}{'KIND':<8}{'RENTABILIDADE':<16}{'CHAVE DE PREÇO':<24}"
          + "".join(f"{c:<{larg}}" for c in cab_org))
    print("─" * (34 + 10 + 13 + 24 + larg * len(origens)))

    barrados, motivos, vazou, incoerentes = collections.Counter(), {}, [], []
    for pn in pns:
        try:
            L = _analisar(pn)
        except Exception as e:                                   # noqa: BLE001
            # ⚠ ABORTA no primeiro erro, e NÃO segue. Bug meu de 2026-09-09:
            # antes isto era `continue`, então os 29 PNs falharam, os contadores
            # ficaram todos em zero e o script concluiu ✓ VERDE. É o zero
            # silencioso do `audit_category_codes` outra vez — e justamente no
            # script cujo trabalho é pegar esse tipo de coisa. Continuar também
            # é inútil no Postgres: o 1º erro aborta a transação e todo o resto
            # vira "current transaction is aborted".
            print(f"\n✗ ERRO ao analisar {pn}: {type(e).__name__}: {e}")
            print("\n  Parando aqui. Resultado parcial não vale como aprovação —\n"
                  "  contador zerado por erro é indistinguível de 'nada barrado'.")
            return False
        celulas = []
        for origem, _r in origens:
            veredito, motivo = L['por_origem'][origem]
            if veredito == 'BARRADO':
                barrados[origem] += 1
                motivos.setdefault(motivo, 0)
                motivos[motivo] += 1
            # ── a checagem que faz deste passo um TESTE, e não só um relatório ──
            # Se o chip ENTRA, a tabela do admin tem que concordar. Não é a
            # política reimplementada: a resposta vem da MESMA linha do banco
            # que o `bloqueio_de_origem` lê. Pega o caso em que o motor deixa
            # passar algo que a régua fechou — que é o estrago mais caro aqui,
            # porque não gera erro nenhum: o chip só entra no lote errado.
            if veredito == 'ENTRA' and L['kind'] not in ('—', 'none'):
                linha_tab = PoliticaOrigemTipo.objects.filter(
                    origin=origem, kind=L['kind']).first()
                if linha_tab is not None and not linha_tab.permitido:
                    incoerentes.append((pn, origem, L['kind']))
            marca = {'ENTRA': '✓ entra', 'BARRADO': '✗ BARRADO',
                     'DESCARTE': '↯ descarte', 'FILA': '⏳ fila',
                     'DESCONHECIDO': '? desconh.', 'não lança': '· não lança'}[veredito]
            celulas.append(f"{marca:<{larg}}")
            # vazamento das 3 colunas?
            dest, rent, chave = L['colunas_por_origem'][origem]
            if (dest, rent, chave) != (L['destino'], L['rentab'], L['chave']):
                vazou.append((pn, origem, (dest, rent, chave),
                              (L['destino'], L['rentab'], L['chave'])))
        print(f"{L['pn'][:21]:<22}{L['tipo'][:11]:<12}{L['kind']:<8}"
              f"{L['rentab']:<16}{L['chave'][:23]:<24}" + "".join(celulas))

    print("═" * (34 + 10 + 13 + 24 + larg * len(origens)))
    print("\nLEGENDA  ✓ entra = vira linha de estoque · ✗ BARRADO = origem errada "
          "(volta pra bancada)\n"
          "         ↯ descarte = sucata (gera RejectedEntry de auditoria) · "
          "⏳ fila = PN não confirmado\n"
          "         ? desconh. = sem specs · · não lança = rentabilidade não avaliada")

    if motivos:
        print("\nMENSAGENS QUE O OPERADOR VÊ:")
        for m, n in sorted(motivos.items(), key=lambda x: -x[1]):
            print(f"   {n:>3}×  {m}")

    print("\nBARRADOS POR ORIGEM (nesta amostra):")
    for origem, rotulo in origens:
        print(f"   {str(rotulo):<22} {barrados.get(origem, 0)}")

    # ── o motor concorda com a tabela? ───────────────────────────────────────
    print("\nMOTOR × TABELA DO ADMIN:")
    if incoerentes:
        print(f"   ✗ {len(incoerentes)} chip(s) ENTRAM numa origem que a tabela "
              "FECHOU. A régua está no banco e o motor não obedeceu:")
        for pn, origem, kind in incoerentes[:10]:
            print(f"     {pn} ({kind}) entrou em {origem}, que está fechado pra {kind}")
        return False
    print("   ✓ nenhum chip entra onde a tabela fechou.")

    # ── a prova das três colunas ─────────────────────────────────────────────
    print("\nAS TRÊS COLUNAS (destino · rentabilidade · chave de preço):")
    if vazou:
        print(f"   ✗ {len(vazou)} caso(s) em que a origem MUDOU alguma das três. "
              "Isto é bug — a torneira não pode encostar nelas:")
        for pn, origem, com, sem in vazou[:10]:
            print(f"     {pn} em {origem}: {sem} → {com}")
        return False
    print("   ✓ idênticas em toda origem — a torneira decide se GRAVA, "
          "não o que o chip É.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
def censo(limite):
    """Varre o catálogo e conta: se eu ligar isso hoje, quanto material cada
    origem passa a barrar? O número que decide se a régua está certa."""
    from chips.engine import classify
    from chips.models import KnownPart
    from estoque.models import Lot
    from estoque.politica_origem import bloqueio_de_origem
    from estoque.views import (_compute_gateway, _has_capacity, _price_key_fields)

    qs = (KnownPart.objects
          .filter(review_status='approved', confidence__in=('confirmed', 'manual'))
          .exclude(part_number='').order_by('part_number')
          .values_list('part_number', flat=True))
    total = qs.count()
    if limite <= 0:
        limite = total
        print(f"Catálogo aprovado e autoritativo: {total} PN(s). Varrendo TODOS.\n")
    else:
        # ⚠ o corte é ALFABÉTICO (order_by part_number), não aleatório: 4000 de
        # 8867 deixa marcas inteiras de fora (Micron MT*, Nanya NT*, Toshiba
        # TH*, Winbond W*) e ENVIESA a contagem por tipo. Bug meu de 2026-09-09,
        # quando o padrão era 4000 e o relatório não avisava.
        print(f"Catálogo aprovado e autoritativo: {total} PN(s).\n"
              f"⚠ Varrendo só {limite} — e o corte é ALFABÉTICO, não aleatório:\n"
              f"  marcas inteiras podem ficar de fora e a conta por tipo sai\n"
              f"  enviesada. Para decidir régua, rode SEM --limite.\n")
    if total == 0:
        print("✗ ZERO — sem catálogo não há censo. Se isto é produção, é ALARME.")
        return False

    origens = _origens()
    por_origem = {o: collections.Counter() for o, _ in origens}
    kind_barrado = {o: collections.Counter() for o, _ in origens}
    vistos = 0
    for pn in qs.iterator(chunk_size=500):
        if vistos >= limite:
            break
        vistos += 1
        try:
            r = classify(pn)
            for k in ('chip_type', 'subtype', 'capacity', 'dram_density',
                      'interface', 'brand', 'emcp_ram', 'emcp_nand',
                      'classification_source'):
                r.setdefault(k, '')
            has_cap = _has_capacity(r)
            kind = _price_key_fields(r).get('price_kind') or 'none'
        except Exception as e:                                   # noqa: BLE001
            # mesma lição do `matriz`: no Postgres o 1º erro aborta a transação,
            # então "continuar" só produz um relatório de zeros com cara de OK.
            print(f"\n✗ ERRO no censo, em {pn}: {type(e).__name__}: {e}")
            print(f"  Parando com {vistos} de {total} varridos — censo pela "
                  "metade não é censo.")
            return False
        try:
            gs = {o: _compute_gateway(r, has_cap, lot=Lot(origin=o))
                  for o, _rot in origens}
        except Exception as e:                                   # noqa: BLE001
            print(f"\n✗ ERRO no censo, na régua de {pn}: {type(e).__name__}: {e}")
            print(f"  Parando com {vistos} de {total} varridos — censo pela "
                  "metade não é censo.")
            return False
        for origem, _rot in origens:
            g = gs[origem]
            # mesma ordem do add_chip — ver o comentário em `_analisar`
            if   g['destination'] == 'desconhecido':  por_origem[origem]['desconhecido'] += 1
            elif g['destination'] == 'fila':          por_origem[origem]['fila'] += 1
            elif g['destination'] == 'reprovado':     por_origem[origem]['descarte'] += 1
            elif g['profitable'] != 'RENTÁVEL':       por_origem[origem]['nao_lanca'] += 1
            elif g['origem_bloqueada']:
                por_origem[origem]['BARRADO'] += 1
                kind_barrado[origem][kind] += 1
            else:                                     por_origem[origem]['entra'] += 1

    print(f"Varridos: {vistos}\n")
    ordem = ['entra', 'BARRADO', 'descarte', 'fila', 'desconhecido', 'nao_lanca', 'erro']
    print(f"{'ORIGEM':<24}" + "".join(f"{c:>14}" for c in ordem))
    print("─" * (24 + 14 * len(ordem)))
    for origem, rotulo in origens:
        c = por_origem[origem]
        print(f"{str(rotulo)[:23]:<24}" + "".join(f"{c.get(k, 0):>14}" for k in ordem))

    # ── a invariante que teria pegado o bug da ORDEM sozinha ─────────────────
    # `descarte`, `fila`, `desconhecido` e `nao_lanca` são decididos ANTES da
    # origem entrar na conversa — então TÊM que ser idênticos nas três colunas.
    # Só `entra` e `BARRADO` podem variar. Foi exatamente esta assinatura que
    # denunciou a ordem errada em 2026-09-09: nao_lanca deu 159 / 52 / 160,
    # três números onde só podia haver um. Agora o script fala em vez de eu ter
    # que reparar na tabela.
    print("\nINVARIANTE (o que NÃO depende da origem):")
    sujo = False
    for etapa in ('descarte', 'fila', 'desconhecido', 'nao_lanca'):
        vals = {str(rot): por_origem[o].get(etapa, 0) for o, rot in origens}
        if len(set(vals.values())) > 1:
            sujo = True
            print(f"   ✗ '{etapa}' difere entre origens: {vals}")
            print("     Isto é decidido ANTES da origem — se difere, a ORDEM do "
                  "funil neste script\n     não bate com a do add_chip, e o "
                  "relatório está mentindo.")
    if not sujo:
        print("   ✓ descarte, fila, desconhecido e nao_lanca idênticos nas três "
              "origens —\n     só `entra` e `BARRADO` variam, que é o esperado.")

    print("\nO QUE CADA ORIGEM BARRA, POR TIPO:")
    algum = False
    for origem, rotulo in origens:
        if not kind_barrado[origem]:
            print(f"   {str(rotulo):<22} nada")
            continue
        algum = True
        detalhe = ', '.join(f"{k}={n}" for k, n in
                            sorted(kind_barrado[origem].items(), key=lambda x: -x[1]))
        print(f"   {str(rotulo):<22} {detalhe}")

    if sujo:
        return False
    if algum:
        print("\n⚠ Cada número acima é material que o sistema JÁ CONHECE e JÁ AVALIOU\n"
              "  como rentável, e que passaria a ser recusado naquele tipo de lote.\n"
              "  Se algum tipo aí não deveria estar sendo barrado, a correção é um\n"
              "  clique no admin (Estoque → Política de origem × tipo) — sem deploy.")
    return True


if __name__ == '__main__':
    main()
