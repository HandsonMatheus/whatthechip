# -*- coding: utf-8 -*-
"""
MEDIR_pratica_origem.py — READ-ONLY. A PRÁTICA, não o catálogo.

O `TESTAR_bancada.py --censo` mede o CATÁLOGO: "dos meus PNs conhecidos,
quantos cada origem barraria". Isso é composição de catálogo — é natural que
1583 DDRs sejam barrados em lote de celular, porque DDR não vai em celular.

Esta pergunta é outra, e é a que decide a régua:

    das entradas de estoque que REALMENTE existem, quantas estão numa origem
    que a tabela fecha — e elas estão CONCENTRADAS ou ESPALHADAS?

A diferença é tudo:
  · concentradas em 2-3 lotes → contaminação conhecida, lote mal separado;
  · espalhadas por muitos lotes e muitas datas → não é engano, é PADRÃO. Aquele
    tipo chega naquela origem de verdade, e a régua está prestes a recusar
    material bom na bancada.

Foi assim que o LPDDR em PCB apareceu (foto do comprador, 2026-09-08). Este
script procura o mesmo sinal no seu próprio histórico, em vez de esperar a
próxima foto.

    python MEDIR_pratica_origem.py

Não escreve nada. Roda em transação revertida.

⚠ O histórico NÃO é veredito: o dono já disse que os lotes misturados estavam
errados. O que este script entrega é a FORMA do erro — e forma espalhada por
dezenas de lotes ao longo de meses raramente é erro.
"""
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django                                                    # noqa: E402
django.setup()

from django.db import connection, transaction                    # noqa: E402


def _tabela_existe_ou_sai():
    if 'estoque_politicaorigemtipo' in connection.introspection.table_names():
        return
    print("⏸  A tabela da torneira ainda NÃO existe neste banco. Rode:\n\n"
          "       python manage.py migrate estoque\n")
    sys.exit(2)


def main():
    from estoque.models import InventoryEntry, Lot, PoliticaOrigemTipo
    from pricing.models import KINDS
    from tenancy.models import Company
    from tenancy.scope import company_scope

    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}\n")
    _tabela_existe_ou_sai()

    fechado = {(l.origin, l.kind) for l in
               PoliticaOrigemTipo.objects.filter(permitido=False)}
    if not fechado:
        print("A tabela não fecha nada. Nada a medir.")
        return 0

    # (origem, kind) → {linhas, unidades, lotes:set, primeira, ultima}
    viol = collections.defaultdict(
        lambda: {'linhas': 0, 'un': 0, 'lotes': set(), 'primeira': None,
                 'ultima': None, 'exemplos': []})
    total_linhas = total_un = sem_chave = 0
    lotes_por_origem = collections.Counter()

    empresas = list(Company.objects.all())
    if not empresas:
        print("✗ ZERO empresas. Sem escopo não há leitura — e zero silencioso\n"
              "  aqui seria 'está tudo limpo' sobre nada. Pare e olhe.")
        return 1

    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            for empresa in empresas:
                with company_scope(empresa):
                    for e in (InventoryEntry.objects
                              .select_related('lot').iterator(chunk_size=500)):
                        total_linhas += 1
                        total_un += e.quantity
                        origem = (e.lot.origin or '').strip()
                        kind = (e.price_kind or '').strip()
                        lotes_por_origem[origem] += 0     # garante a chave
                        if not kind or kind not in KINDS:
                            sem_chave += 1
                            continue
                        if (origem, kind) not in fechado:
                            continue
                        v = viol[(origem, kind)]
                        v['linhas'] += 1
                        v['un'] += e.quantity
                        v['lotes'].add(e.lot.code)
                        quando = e.added_at
                        v['primeira'] = min(v['primeira'] or quando, quando)
                        v['ultima'] = max(v['ultima'] or quando, quando)
                        if len(v['exemplos']) < 3:
                            v['exemplos'].append(e.part_number)
    finally:
        transaction.savepoint_rollback(sid)

    if total_linhas == 0:
        print("✗ ZERO entradas de estoque varridas em TODAS as empresas.\n"
              "  Isto não é 'está limpo' — é leitura que não aconteceu. Pare.")
        return 1

    print(f"Entradas varridas: {total_linhas} linhas · {total_un} unidades · "
          f"{len(empresas)} empresa(s)")
    print(f"Sem chave de preço (legado / fora do mercado): {sem_chave} "
          f"({sem_chave / total_linhas * 100:.0f}%) — fora desta regra\n")

    if not viol:
        print("✓ NENHUMA entrada existente está numa origem que a tabela fecha.\n"
              "  A régua descreve a prática. Pode seguir.")
        return 0

    print("═" * 104)
    print(f"{'ORIGEM × TIPO':<20}{'LINHAS':>8}{'UNID.':>9}{'LOTES':>7}"
          f"{'PRIMEIRA':>12}{'ÚLTIMA':>12}   FORMA")
    print("─" * 104)
    espalhados = []
    for (origem, kind), v in sorted(viol.items(), key=lambda x: -x[1]['linhas']):
        n_lotes = len(v['lotes'])
        # A leitura: muitos lotes = padrão; poucos = contaminação pontual.
        if n_lotes >= 5:
            forma = '⚠ ESPALHADO — cheira a padrão, não a engano'
            espalhados.append((origem, kind, n_lotes, v))
        elif n_lotes >= 2:
            forma = '· alguns lotes — olhar um a um'
            espalhados.append((origem, kind, n_lotes, v))
        else:
            forma = '✓ 1 lote só — contaminação pontual'
        print(f"{origem + ' × ' + kind:<20}{v['linhas']:>8}{v['un']:>9}"
              f"{n_lotes:>7}"
              f"{v['primeira'].strftime('%d/%m/%y'):>12}"
              f"{v['ultima'].strftime('%d/%m/%y'):>12}   {forma}")
    print("═" * 104)

    for origem, kind, n_lotes, v in espalhados:
        print(f"\n{origem} × {kind} — {n_lotes} lote(s): "
              f"{', '.join(sorted(v['lotes'])[:8])}"
              f"{' …' if n_lotes > 8 else ''}")
        print(f"   exemplos de PN: {', '.join(v['exemplos'])}")

    if espalhados:
        print("\n" + "─" * 104)
        print("COMO LER: tipo que aparece em MUITOS lotes, ao longo de MESES, "
              "dificilmente é engano\nde separação. É o mesmo sinal que a foto "
              "do comprador deu sobre o LPDDR em PCB.\nAntes de publicar, vale "
              "perguntar ao comprador se aquele tipo chega mesmo naquela\norigem "
              "— e, se chegar, abrir a torneira no admin (sem deploy).")
    else:
        print("\n✓ Todas as violações estão em lote ÚNICO — contaminação "
              "pontual, não padrão.\n  A régua descreve a prática.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
