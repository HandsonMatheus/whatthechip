#!/usr/bin/env python
"""
VERIFICAR_politica_origem.py — READ-ONLY. Confere a torneira origem × tipo
depois da migração (local, staging ou produção).

    python VERIFICAR_politica_origem.py

Não escreve nada. Abre transação e faz rollback no fim, como o
`characterize_baseline` — segurança contra o dedo errado num banco de produção.
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django                                                    # noqa: E402
django.setup()

from django.db import connection, transaction                    # noqa: E402
from estoque.models import Lot, PoliticaOrigemTipo               # noqa: E402
from estoque.politica_origem import bloqueio_de_origem           # noqa: E402
from pricing.models import KINDS                                 # noqa: E402

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


d = connection.settings_dict
print(f"⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST')}\n")

_tabela_existe_ou_sai()

falhou = False
sid = transaction.savepoint()
try:
    with transaction.atomic():
        # ── 1. completude: uma linha para TODA combinação ────────────────────
        origens = [v for v, _ in Lot.ORIGIN_CHOICES]
        esperado = len(origens) * len(KINDS)
        total = PoliticaOrigemTipo.objects.count()
        print(f"1) LINHAS: {total} (esperado {esperado} = "
              f"{len(origens)} origens × {len(KINDS)} tipos)")
        faltando = [f'{o}×{k}' for o in origens for k in sorted(KINDS)
                    if not PoliticaOrigemTipo.objects.filter(origin=o, kind=k).exists()]
        if faltando:
            falhou = True
            print(f"   ✗ FALTANDO {len(faltando)}: {', '.join(faltando)}")
            print("     (sem linha, o bloqueio é FAIL-CLOSED e barra o tipo inteiro)")
        else:
            print("   ✓ tabela completa")

        # ── 2. a régua do dono, literal ──────────────────────────────────────
        print("\n2) TORNEIRA POR ORIGEM:")
        for origem, rotulo in Lot.ORIGIN_CHOICES:
            abertos = sorted(PoliticaOrigemTipo.objects
                             .filter(origin=origem, permitido=True)
                             .values_list('kind', flat=True))
            fechados = sorted(PoliticaOrigemTipo.objects
                              .filter(origin=origem, permitido=False)
                              .values_list('kind', flat=True))
            legada = ' [LEGADA]' if origem in Lot.ORIGIN_LEGACY else ''
            print(f"   {origem:<6}{legada:<10} abre={abertos}")
            print(f"   {'':<16} fecha={fechados}")

        ESPERADO = {'phone': {'emcp', 'umcp', 'emmc', 'ufs', 'lpddr'},
                    'pcb':   {'ddr', 'emmc', 'k9', 'ssd', 'lpddr'}}
        for origem, deveria in ESPERADO.items():
            tem = set(PoliticaOrigemTipo.objects.filter(origin=origem, permitido=True)
                      .values_list('kind', flat=True))
            if tem != deveria:
                falhou = True
                print(f"   ✗ {origem}: esperava {sorted(deveria)}, achei {sorted(tem)}")

        # ── 3. a regra respondendo, ponta a ponta ────────────────────────────
        print("\n3) A REGRA RESPONDENDO:")
        casos = [('phone', 'emcp', 'passa'), ('phone', 'ddr', 'BARRA'),
                 ('pcb', 'ddr', 'passa'),    ('pcb', 'emcp', 'BARRA'),
                 ('phone', 'emmc', 'passa'), ('pcb', 'emmc', 'passa'),
                 ('phone', 'none', 'passa'), ('phone', '', 'passa'),
                 ('marte', 'emcp', 'BARRA')]
        for origem, kind, esperado_txt in casos:
            motivo = bloqueio_de_origem(origem, kind)
            real = 'BARRA' if motivo else 'passa'
            ok = '✓' if real == esperado_txt else '✗'
            if real != esperado_txt:
                falhou = True
            extra = f' → "{motivo}"' if motivo else ''
            print(f"   {ok} {origem:<6} × {kind or '(vazio)':<8} {real}{extra}")
finally:
    transaction.savepoint_rollback(sid)

print("\n" + ("✗ ALGO ESTÁ FORA DO ESPERADO — leia acima antes de liberar a bancada."
              if falhou else
              "✓ Torneira instalada e respondendo como a régua do dono manda."))
sys.exit(1 if falhou else 0)
