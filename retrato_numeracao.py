#!/usr/bin/env python
"""
retrato_numeracao.py — READ-ONLY (não grava NADA no banco).

O "antes" da convenção de identificadores (CONVENCAO_IDENTIFICADORES.md +
PLANO_CONVENCAO_IDENTIFICADORES.md, passo 0 do runbook). Responde às perguntas
que o plano não conseguiu fechar lendo só o código:

  · qual é o código ATUAL de cada empresa, e para que ele vai quando a semente
    virar 4 letras (EMI → EMIN, ERC → EREC);
  · quantos lotes e ordens existem, POR ANO — se houver documento de 2025, o
    reinício anual deixa de ser "não renumera nada";
  · buracos na numeração de cada empresa (D9: ficam como estão, mas é bom saber);
  · como cada documento vai FICAR escrito, antes de qualquer coisa ser gravada;
  · ⚠ ordem cujo ano de criação difere do ano do LOTE — o caso do §2.2/§2.4, que
    é onde a herança do ano muda o número de verdade.

RLS (CLAUDE.md §7): lê dentro de `company_scope(empresa)`. Sem o GUC, num banco
com FORCE RLS o SELECT devolve ZERO linhas EM SILÊNCIO e o retrato sairia vazio
num banco cheio. Local engana — superuser bypassa FORCE.

Uso:
    python retrato_numeracao.py                 # o banco do seu .env (localhost)
    DATABASE_URL="postgresql://…render.com…" python retrato_numeracao.py   # prod
"""
import os
import unicodedata


def semente4(nome, ocupados):
    """A semente de 4 letras do plano (Fase A2), calculada AQUI para poder
    prever o resultado sem depender do código ainda não alterado."""
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', nome or '')
                         if not unicodedata.combining(c)).upper()
    letras = ''.join(c for c in sem_acento if 'A' <= c <= 'Z')
    if len(letras) < 2:
        return ''
    for tentativa in (letras[:4], letras[:3]):
        if len(tentativa) >= 2 and tentativa not in ocupados:
            return tentativa
    for sufixo in 'BCDEFGHIJKLMNOPQRSTUVWXYZ':
        if letras[:3] + sufixo not in ocupados:
            return letras[:3] + sufixo
    return ''


def novo_lot(ano, n):
    return f'LOT-{ano}-{n:04d}'


def novo_so(code, ano, n):
    return f'{code}-SO-{ano}-{n:04d}' if code else f'SO-{ano}-{n:04d}'


def main():
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()

    from django.db import connection
    from django.utils import timezone
    from tenancy.models import Company
    from tenancy.scope import company_scope
    from estoque.models import Lot
    from vendas.models import SalesOrder, Invoice, DocSequence

    d = connection.settings_dict
    print(f'⚠  BANCO-ALVO → name={d.get("NAME")}  host={d.get("HOST") or "localhost"}')
    print('   (somente leitura — este script não escreve nada)\n')

    ano_de = lambda dt: timezone.localtime(dt).year if dt else None

    empresas = list(Company.objects.all().order_by('pk'))
    ocupados = {c.code for c in empresas if c.code}

    print('═══ EMPRESAS — código atual → código de 4 letras ═══')
    previsto = {}
    livres = set()
    for c in empresas:
        novo = c.code if len(c.code) == 4 else semente4(c.name, livres | (ocupados - {c.code}))
        livres.add(novo)
        previsto[c.pk] = novo
        marca = '' if novo == c.code else '   ← MUDA'
        print(f'  #{c.pk} {c.name:<26} slug={c.slug:<20} '
              f'{c.code or "(vazio)":<6} → {novo or "(vazio)":<6}{marca}')

    total_l = total_s = 0
    # ⚠ `.values(...)` e não o objeto inteiro: este script roda ANTES da
    # migração (é para isso que ele serve — retratar o banco que vai receber a
    # mudança), e um SELECT do modelo completo pediria `doc_year`/`ever_closed`,
    # colunas que ainda não existem lá. Lista explícita = funciona nos dois lados.
    CAMPOS_LOTE = ('pk', 'number', 'code_str', 'created_at', 'status')
    CAMPOS_OV = ('pk', 'number', 'code_str', 'created_at',
                 'lot__number', 'lot__created_at')

    for c in empresas:
        with company_scope(c):
            lotes = list(Lot.all_companies.filter(company=c)
                         .order_by('number').values(*CAMPOS_LOTE))
            ordens = list(SalesOrder.all_companies.filter(company=c)
                          .order_by('number').values(*CAMPOS_OV))
            faturas = Invoice.all_companies.filter(company=c).count()
        if not (lotes or ordens or faturas):
            continue
        total_l += len(lotes)
        total_s += len(ordens)
        print(f'\n═══ {c.name}  (código {c.code or "vazio"} → {previsto[c.pk] or "vazio"}) ═══')

        por_ano = {}
        for l in lotes:
            por_ano.setdefault(ano_de(l['created_at']), []).append(l)
        for ano in sorted(por_ano, key=lambda a: (a is None, a)):
            nums = sorted(x['number'] for x in por_ano[ano])
            faltando = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
            print(f'  LOTES {ano}: {len(nums)} un.  nº {min(nums)}–{max(nums)}'
                  + (f'   ⚠ buracos: {faltando}' if faltando else '   sem buracos'))
        # amostra: os 3 primeiros e os 3 últimos quando a lista é longa
        amostra = lotes if len(lotes) <= 6 else lotes[:3] + [None] + lotes[-3:]
        for l in amostra:
            if l is None:
                print(f'        … ({len(lotes) - 6} lote(s) no meio)')
                continue
            a = ano_de(l['created_at'])
            print(f'        {l["code_str"] or "(vazio)":<22} → {novo_lot(a, l["number"]):<15} '
                  f'{l["status"]}  aberto {timezone.localtime(l["created_at"]):%d/%m/%Y}')

        if ordens:
            anos_so = {}
            for o in ordens:
                anos_so.setdefault(ano_de(o['lot__created_at']), []).append(o)
            for ano in sorted(anos_so, key=lambda a: (a is None, a)):
                nums = sorted(x['number'] for x in anos_so[ano])
                print(f'  ORDENS (ano do LOTE) {ano}: {len(nums)} un.  nº {min(nums)}–{max(nums)}')
            for o in ordens:
                a_lote = ano_de(o['lot__created_at'])
                a_prop = ano_de(o['created_at'])
                aviso = '   ⚠ §2.2 — ano do lote ≠ ano da criação' if a_lote != a_prop else ''
                print(f'        {o["code_str"] or "(vazio)":<22} → '
                      f'{novo_so(previsto[c.pk], a_lote, o["number"]):<20} '
                      f'lote {o["lot__number"]}{aviso}')
        if faturas:
            print(f'  FATURAS: {faturas} — NÃO são tocadas por esta entrega (D1)')

    print('\n═══ CONTADORES ═══')
    for c in empresas:
        # ⚠ DENTRO do company_scope. `vendas_docsequence` tem RLS+FORCE: sem o
        # GUC a policy devolve ZERO linhas EM SILÊNCIO, e o retrato diria que
        # não há contador nenhum num banco que tem. O local engana — conexão
        # superuser passa por cima do FORCE (CLAUDE.md §7). Este bloco já saiu
        # errado uma vez contra produção, em 02/09.
        # (o `year` do DocSequence também é coluna nova → values explícito)
        with company_scope(c):
            seqs = list(DocSequence.all_companies.filter(company=c)
                        .values('kind', 'last_number'))
        if c.last_lot_number or seqs:
            print(f'  {c.name}: Company.last_lot_number={c.last_lot_number}'
                  + ''.join(f'  |  DocSequence[{d["kind"]}]={d["last_number"]}'
                            for d in seqs))

    print(f'\nTOTAL: {total_l} lote(s), {total_s} ordem(ns).')
    print('Nada foi gravado.')


if __name__ == '__main__':
    main()
