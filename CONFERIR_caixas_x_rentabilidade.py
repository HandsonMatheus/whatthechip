# -*- coding: utf-8 -*-
"""
CONFERIR_caixas_x_rentabilidade.py — READ-ONLY. As caixas × a régua, NOS DOIS
SENTIDOS.

O `audit_category_codes` responde *"quais caixas existem que a bancada hoje não
criaria?"*. Ele só enxerga o que EXISTE. Este script fecha o círculo — são
quatro perguntas, e duas delas o audit não tem como fazer:

  1. toda caixa VIVA é RENTÁVEL?          (a mesma do audit, agora como asserção)
  2. toda caixa APOSENTADA é NÃO RENTÁVEL? ← o ESPELHO. Se a régua afrouxou (o
     dono baixou um limiar no admin), uma aposentada pode ter voltado a valer, e
     ela fica marcada como morta até um chip daquela categoria aparecer na
     bancada — `label_for_key` só reativa na aprovação. Enquanto isso a
     categoria some das telas do comprador, e material vendável não é ofertado.
  3. toda categoria COTADA no grid tem caixa VIVA? ← a que MAIS custa dinheiro.
     Categoria com preço e sem caixa faz o chip entrar como **H-00 HOLD**
     ("separar para análise"): o comprador paga por ela, a bancada reconhece,
     e o material trava sem rótulo.
  4. toda caixa consta da TABELA FUNDADORA (pricing/convention.py)?

⚠ LIMITE HONESTO, herdado do audit: em eMCP/uMCP a chave carrega SÓ o NAND
("unified by cap", v3.1). Geração e tamanho da RAM não estão nela, então o
veredito aqui isola o critério de NAND — a RAM é sintetizada como aprovada de
propósito. Um eMCP com NAND boa e LPDDR2 é reprovado NO CHIP (bancada), não na
caixa. Isto não é imprecisão do script: é o que a chave sabe.

O veredito NÃO é reimplementado em lugar nenhum — o `result_sintetico` e o
`assess_profitability` vêm dos módulos de verdade, e leem a ProfitabilityConfig
VIVA. Mexeu no limiar do admin, este relatório muda junto.

    python CONFERIR_caixas_x_rentabilidade.py
    python CONFERIR_caixas_x_rentabilidade.py --tudo   # lista as 77, uma a uma
    python CONFERIR_caixas_x_rentabilidade.py --simular-aposentadoria

⚠ SOBRE O `--simular-aposentadoria`: sem ele, a checagem 3 responde *hoje*, e
  hoje as caixas que a checagem 1 reprova AINDA ESTÃO VIVAS — uma delas que
  esteja cotada no grid não aparece na checagem 3, só apareceria DEPOIS do
  `retire_category_codes --commit`, com o material já travado. Com a flag, a
  pergunta vira *"e depois de aposentar?"* — que é a que decide se pode rodar
  o commit. A flag não grava nada: ela só tira essas chaves do conjunto de
  vivas em memória.

Não escreve nada. Roda em transação revertida.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django                                                    # noqa: E402
django.setup()

from django.db import connection, transaction                    # noqa: E402


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--tudo', action='store_true',
                    help='lista TODAS as caixas com o veredito, não só os problemas')
    ap.add_argument('--simular-aposentadoria', action='store_true',
                    dest='simular',
                    help='responde a checagem 3 como se o retire_category_codes '
                         '--commit JÁ tivesse rodado (nada é gravado)')
    args = ap.parse_args()

    # Fonte única: os mesmos helpers que o audit e o retire usam.
    from pricing.management.commands.audit_category_codes import (
        result_sintetico, _chaves_da_convencao)
    from chips.engine import assess_profitability
    from pricing.models import CategoryCode, Price, STATUS_QUOTED
    from tenancy.scope import platform_scope

    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}")
    print("   MODO → " + ("SIMULANDO a aposentadoria das reprovadas (nada gravado)"
                          if args.simular else "estado de HOJE") + "\n")

    problemas = []
    sid = transaction.savepoint()
    try:
        with transaction.atomic():
            caixas = list(CategoryCode.objects.all().order_by('kind', 'code'))
            if not caixas:
                print("✗ ZERO caixas no banco. Isto não é 'está tudo certo' — é\n"
                      "  leitura que não aconteceu, ou banco vazio. Pare e olhe.")
                return 1

            convencao = _chaves_da_convencao()
            vivas, aposentadas = [], []
            for c in caixas:
                chave = (c.kind, c.gen, c.tier_value, c.tier_unit)
                veredito = assess_profitability(result_sintetico(*chave))
                alvo = aposentadas if c.retired_at is not None else vivas
                alvo.append((c, chave, veredito))

            print(f"{len(caixas)} caixa(s) · {len(vivas)} viva(s) · "
                  f"{len(aposentadas)} aposentada(s)")

            if args.tudo:
                print("\n" + "═" * 78)
                print(f"{'CÓDIGO':<8}{'TIPO':<7}{'GERAÇÃO':<9}{'FAIXA':<12}"
                      f"{'ESTADO':<13}{'VEREDITO HOJE':<15}CONVENÇÃO")
                print("─" * 78)
                for c, chave, v in sorted(vivas + aposentadas,
                                          key=lambda x: x[0].label):
                    estado = 'aposentada' if c.retired_at else 'viva'
                    conv = 'ok' if chave in convencao else 'AUSENTE'
                    faixa = (f'{c.tier_value:g}{c.tier_unit}' if c.tier_unit else '—')
                    print(f"{c.label:<8}{c.kind:<7}{c.gen or '—':<9}{faixa:<12}"
                          f"{estado:<13}{v:<15}{conv}")
                print("═" * 78)

            # ── 1. caixa VIVA reprovada pela régua ───────────────────────────
            maus = [(c, v) for c, _k, v in vivas if v == 'NÃO RENTÁVEL']
            print(f"\n1) CAIXA VIVA que a régua REPROVA: {len(maus)}")
            if maus:
                problemas.append('caixa viva reprovada')
                for c, v in maus:
                    print(f"   ⛔ {c.label}  {c.kind} {c.gen or '—'} "
                          f"{c.tier_value:g}{c.tier_unit}")
                print("      → aposentar: python manage.py retire_category_codes --commit")
            else:
                print("   ✓ nenhuma — toda caixa em circulação é vendável hoje.")

            # ── 2. caixa APOSENTADA que voltou a valer ───────────────────────
            ressuscitadas = [(c, v) for c, _k, v in aposentadas
                             if v != 'NÃO RENTÁVEL']
            print(f"\n2) CAIXA APOSENTADA que a régua HOJE aprova: {len(ressuscitadas)}")
            if ressuscitadas:
                problemas.append('aposentada que voltou a valer')
                for c, v in ressuscitadas:
                    print(f"   ⚠ {c.label}  {c.kind} {c.gen or '—'} "
                          f"{c.tier_value:g}{c.tier_unit}  → {v}")
                print("      A régua afrouxou desde a aposentadoria. A categoria só\n"
                      "      volta sozinha quando um chip dela for aprovado na bancada;\n"
                      "      até lá ela não aparece pro comprador. Reativar à mão:\n"
                      "      python manage.py retire_category_codes --reativar <CÓDIGO> --commit")
            else:
                print("   ✓ nenhuma — o que está aposentado continua sendo sucata.")

            # ── 3. categoria COTADA sem caixa viva ───────────────────────────
            with platform_scope():
                total_precos = Price.all_companies.count()
                cotadas = set(Price.all_companies
                              .filter(status=STATUS_QUOTED)
                              .exclude(tier_value=None)
                              .values_list('kind', 'gen', 'tier_value', 'tier_unit'))
            if total_precos == 0:
                print("\n3) ✗ ZERO linhas de preço lidas — leitura barrada (RLS sem GUC)\n"
                      "     ou grid vazio. NÃO conclua 'sem lacuna' a partir disto.")
                problemas.append('grid ilegível')
            else:
                # ⚠ Com --simular, as reprovadas saem do conjunto de vivas AQUI,
                #   em memória. É o que responde a pergunta que decide o commit:
                #   "aposentar estas trava alguma categoria que o comprador
                #   paga?". Sem a flag, elas ainda contam como vivas e uma
                #   cotada entre elas ficaria INVISÍVEL até o estrago acontecer.
                simuladas = ([(c, k, v) for c, k, v in vivas if v == 'NÃO RENTÁVEL']
                             if args.simular else [])
                chaves_simuladas = {k for _c, k, _v in simuladas}
                vivas_chaves = {k for _c, k, _v in vivas} - chaves_simuladas
                mortas = aposentadas + simuladas
                sem_caixa = sorted(cotadas - vivas_chaves)
                print(f"\n3) CATEGORIA COTADA no grid SEM caixa viva: {len(sem_caixa)}"
                      f"   (de {len(cotadas)} cotadas · {total_precos} linhas no grid)")
                if args.simular:
                    print(f"   [simulando {len(simuladas)} aposentadoria(s)]")
                if sem_caixa:
                    problemas.append('categoria cotada ficaria sem caixa'
                                     if args.simular else 'categoria cotada sem caixa')
                    for kind, gen, tv, tu in sem_caixa:
                        chave = (kind, gen, tv, tu)
                        morta = next((c for c, k, _v in mortas if k == chave), None)
                        if morta is None:
                            extra = '  ← não existe caixa nenhuma'
                        elif chave in chaves_simuladas:
                            extra = f'  ← É UMA DAS QUE VOCÊ IA APOSENTAR ({morta.label})'
                        else:
                            extra = f'  ← existe mas está APOSENTADA ({morta.label})'
                        print(f"   ⚠ {kind} {gen or '—'} {tv:g}{tu}{extra}")
                    if chaves_simuladas & set(sem_caixa):
                        print("      ⛔ NÃO RODE o retire_category_codes --commit ainda.\n"
                              "      O comprador PAGA por esta categoria: aposentar a caixa\n"
                              "      faz o chip dela entrar como H-00 HOLD, sem rótulo, e\n"
                              "      some da tela dele. Ou tire o preço do grid primeiro, ou\n"
                              "      poupe esta caixa (a régua e o grid discordam — decida\n"
                              "      qual dos dois está errado).")
                    else:
                        print("      O comprador PAGA por esta categoria e o chip dela entra\n"
                              "      como H-00 HOLD, sem rótulo — material vendável travado.")
                elif args.simular:
                    print(f"   ✓ nenhuma — aposentar as {len(simuladas)} NÃO trava\n"
                          "     nenhuma categoria que o comprador paga. Sinal verde para\n"
                          "     o retire_category_codes --commit.")
                else:
                    print("   ✓ nenhuma — tudo que tem preço tem caixa.")

            # ── 4. caixa fora da tabela fundadora ────────────────────────────
            fora = [c for c, k, _v in vivas if k not in convencao]
            print(f"\n4) CAIXA VIVA fora da TABELA FUNDADORA: {len(fora)}")
            if fora:
                problemas.append('caixa fora da convenção')
                for c in fora:
                    print(f"   ➕ {c.label}  {c.kind} {c.gen or '—'} "
                          f"{c.tier_value:g}{c.tier_unit}")
                print("      Nasceram na bancada e faltam no registro. Anexe em\n"
                      "      pricing/convention.py (NUNCA renumere o que já existe).")
            else:
                print("   ✓ nenhuma — banco e convenção contam a mesma história.")
    finally:
        transaction.savepoint_rollback(sid)

    print("\n" + "─" * 78)
    print("⚠ eMCP/uMCP: a chave carrega só o NAND, então o veredito das caixas A e C\n"
          "  isola o critério de NAND. A geração da RAM é julgada NO CHIP, na bancada.")
    if problemas:
        print(f"\n✗ {len(problemas)} problema(s): {', '.join(problemas)}")
        return 1
    print("\n✓ As caixas e a régua de rentabilidade contam a MESMA história,\n"
          "  nos dois sentidos.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
