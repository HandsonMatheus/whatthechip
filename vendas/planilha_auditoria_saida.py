# -*- coding: utf-8 -*-
"""
planilha_auditoria_saida.py — PINTAR a planilha dele, no arquivo dele.

A primeira versão disto era um comparativo de 17 colunas, num arquivo novo. O
dono leu e respondeu (08/09/2026): *"impossível ler o seu arquivo, informação
demais — simplesmente pinte na planilha dele mesmo no que foi que ele mexeu,
adicione uma coluna com o preço dele e outra com o preço do sistema e avise
se subiu ou baixou, só isso"*.

A lição vale além deste arquivo: uma auditoria completa não é uma auditoria
legível. Quem confere já conhece a planilha — cada linha, onde cada coluna
fica, o que cada caixa quer dizer. Um documento NOVO obriga a reaprender tudo
isso para chegar à única informação que faltava. Pintar o documento que ele já
conhece põe a informação exatamente onde a pergunta nasce.

Então: abrimos o .xlsx que ele devolveu, marcamos a célula do ¥ que ele mudou
(vermelho = baixou, verde = subiu), acrescentamos três colunas ao lado —
¥ SISTEMA · ¥ DELE · SUBIU/BAIXOU — e salvamos numa CÓPIA. O original nunca é
tocado: é a prova do que ele mandou.

⚠ Carregamos o arquivo DUAS vezes, de propósito: `data_only=True` para LER (o
  que interessa é o valor) e `data_only=False` para PINTAR e salvar. Salvar a
  versão `data_only=True` gravaria os valores em cima das fórmulas — apagando,
  em silêncio, as somas de quem abrir depois.
"""

from decimal import Decimal

from vendas.planilha import (BRANCO, FMT_RMB, GREEN_10, GREEN_50,
                             INK_100, MONO, RED_10, RED_60)

ZERO = Decimal('0.00')

BAIXOU, SUBIU = 'BAIXOU', 'SUBIU'

#: Nome humano de cada diferença — para o relatório longo (`--detalhe`).
FRASE = {
    'preco': '¥ unitário alterado',
    'preco_apagado': '¥ unitário apagado',
    'enviados': 'quantidade enviada alterada',
    'recusa': 'recusa declarada',
    'conta_aprovados': 'aprovados ≠ enviados − recusa',
    'conta_resultado': '¥ resultado ≠ aprovados × ¥',
}

#: O que a célula da planilha diz, em duas palavras. É outra coisa que a
#: `FRASE`, de propósito: ali cabe a explicação, aqui cabe um aviso — e um
#: aviso que transborda a célula esconde o "BAIXOU ¥8" da linha de baixo.
AVISO_CURTO = [
    ('preco_apagado', '¥ APAGADO'),
    ('enviados', 'QTD MEXIDA'),
    ('conta_aprovados', 'CONTA NÃO FECHA'),
    ('conta_resultado', 'CONTA NÃO FECHA'),
]

#: As colunas que entram, e ELAS ENTRAM NO MEIO — não no fim.
#:
#: ⚠ TERCEIRA rodada com o dono neste mesmo arquivo, e as três falhas foram de
#:   LUGAR e NOME, nunca de conta:
#:     1. comparativo de 17 colunas em arquivo novo → *"impossível ler"*;
#:     2. as colunas certas chamadas `¥ SISTEMA`/`¥ DELE` → ele pediu *"uma
#:        coluna com o preço COMO ERA ANTES"*, que era aquela;
#:     3. acrescentadas DEPOIS da última coluna dele (M/N/O) → *"não veio
#:        coluna de antes e agora não"*. Vieram; estavam fora da tela.
#:
#:   A lição: informação a três colunas de rolagem do dado que ela explica não
#:   existe. `¥ ANTES` entra ENCOSTADA à esquerda do ¥ unitário dele — o par
#:   fica no mesmo olhar, e é o par que responde "o que ele baixou".
ANTES = '¥ ANTES'
TOT_ANTES, TOT_AGORA = '¥ TOTAL ANTES', '¥ TOTAL AGORA'

#: Nome humano de cada diferença — para o relatório longo (`--detalhe`).
FRASE = {
    'preco': '¥ unitário alterado',
    'preco_apagado': '¥ unitário apagado',
    'enviados': 'quantidade enviada alterada',
    'recusa': 'recusa declarada',
    'conta_aprovados': 'aprovados ≠ enviados − recusa',
    'conta_resultado': '¥ resultado ≠ aprovados × ¥',
}


def _f(v):
    """Decimal → float. NÚMERO, nunca texto: '¥ 15,00' parece igual e não
    soma, e planilha que não soma é print (mesma regra do `planilha.py`)."""
    return None if v is None else float(v)


def _pinta(cel, fundo, tinta, negrito=False):
    from openpyxl.styles import Font, PatternFill
    cel.fill = PatternFill('solid', fgColor=fundo)
    cel.font = Font(name=MONO, size=cel.font.size or 11, color=tinta,
                    bold=negrito)


def _titulo(ws, r, c, texto):
    from openpyxl.styles import Alignment, Font, PatternFill
    cel = ws.cell(r, c, texto)
    cel.font = Font(name=MONO, bold=True, color=BRANCO, size=9)
    cel.fill = PatternFill('solid', fgColor=INK_100)
    cel.alignment = Alignment(horizontal='right', vertical='center',
                              wrap_text=True)
    ws.column_dimensions[cel.column_letter].width = 14
    return cel


def _abre_espaco(ws, col_unit):
    """Insere 1 coluna à ESQUERDA do ¥ unitário e 2 à direita.

    Devolve ``(c_antes, c_agora, c_tot_antes, c_tot_agora, desloca)``, em que
    `desloca(c)` diz onde foi parar a coluna que estava em `c`.

    ⚠ `insert_cols` move as células (com estilo) mas NÃO move as LARGURAS de
      coluna, que são um dicionário à parte indexado por letra. Sem remontá-las
      a planilha sai com a largura da coluna errada em tudo à direita do
      preço — e uma coluna estreita demais mostra `####` em vez do número.
      Este arquivo não tem merge, fórmula, validação nem formatação
      condicional (conferido antes de escolher este caminho); se um dia tiver,
      `insert_cols` também não os desloca.
    """
    largura = {c: d.width for c, d in ws.column_dimensions.items() if d.width}
    ws.insert_cols(col_unit, 1)           # o ¥ unitário dele vai para +1
    ws.insert_cols(col_unit + 2, 2)       # e os dois totais entram depois

    def desloca(c):
        return c if c < col_unit else (c + 1 if c == col_unit else c + 3)

    from openpyxl.utils import column_index_from_string as num
    from openpyxl.utils import get_column_letter as letra
    # `width = None` é recusado pelo descritor do openpyxl (espera float); e
    # deixar as antigas no lugar somaria a largura velha à nova na mesma letra.
    # O holder é um dict de propriedades de coluna e aqui só há largura —
    # limpar e remontar é exato. (Coluna escondida ou agrupada se perderia:
    # este arquivo não tem, e o `insert_cols` também não as deslocaria.)
    ws.column_dimensions.clear()
    for c, w in largura.items():
        ws.column_dimensions[letra(desloca(num(c)))].width = w
    return (col_unit, col_unit + 1, col_unit + 2, col_unit + 3, desloca)


def pinta_planilha(entrada, saida, achados, resumo):
    """Escreve em `saida` a planilha dele com quatro colunas onde ele lê preço.

    ``¥ ANTES │ ¥ unit. (dele) │ ¥ TOTAL ANTES │ ¥ TOTAL AGORA`` — o par de
    unitários encostado, e ao lado o que cada um dá no total da linha. A célula
    do ¥ que ele mudou fica vermelha (baixou) ou verde (subiu); a de ENVIADOS,
    se ele a reescreveu; a de APROVADOS, se a conta dele não fecha.

    Os totais somam por MARCA na faixa e no rodapé, com `SUM` de verdade — na
    coluna dele os subtotais existem, e duas colunas novas em branco ali
    quebrariam a linha que soma.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter as letra

    wb = openpyxl.load_workbook(entrada)   # data_only=False: ver ⚠ do módulo
    ws = wb.worksheets[0]
    papeis = resumo['papeis']
    c_antes, c_agora, c_ta, c_tg, desloca = _abre_espaco(ws, papeis['unit'])
    col = {papel: desloca(c) for papel, c in papeis.items()}

    _titulo(ws, resumo['cabecalho'], c_antes, ANTES)
    _titulo(ws, resumo['cabecalho'], c_ta, TOT_ANTES)
    _titulo(ws, resumo['cabecalho'], c_tg, TOT_AGORA)

    baixou = subiu = 0
    for a in achados:
        if a['tipo_achado'] != 'linha':
            continue
        r = a['planilha']['linha']
        antes, agora = a['banco']['unit'], a['planilha']['unit']
        mexeu = antes is not None and agora is not None and agora != antes
        desceu = mexeu and agora < antes

        for c, v in ((c_antes, _f(antes)), (c_ta, _f(a['valor_ov'])),
                     (c_tg, _f(a['valor_dele']))):
            cel = ws.cell(r, c, v)
            cel.number_format = FMT_RMB
            cel.font = Font(name=MONO, size=10, bold=mexeu,
                            color=(RED_60 if desceu else GREEN_50)
                            if mexeu else None)
            cel.alignment = Alignment(horizontal='right')

        if mexeu:
            # A CÉLULA DELE, onde ele a escreveu. É o ponto: ele corre o olho
            # pela coluna que já conhece e vê quais números são dele.
            _pinta(ws.cell(r, c_agora), RED_10 if desceu else GREEN_10,
                   RED_60 if desceu else GREEN_50, negrito=True)
            baixou, subiu = baixou + desceu, subiu + (not desceu)
        # Duas células dele que também merecem marca, e nenhuma é preço:
        # ENVIADOS é o que o cliente despachou (a recusa tem coluna própria);
        # APROVADOS marcado significa que aprovados ≠ enviados − recusa, ou
        # que o ¥ resultado não é aprovados × ¥ — a conta dele não fecha.
        if 'enviados' in a['diffs'] and col.get('enviados'):
            _pinta(ws.cell(r, col['enviados']), RED_10, RED_60)
        if ({'conta_aprovados', 'conta_resultado'} & set(a['diffs'])
                and col.get('aprovados')):
            _pinta(ws.cell(r, col['aprovados']), RED_10, RED_60)

    _soma(ws, resumo, achados, (c_ta, c_tg), letra)
    wb.save(saida)
    return dict(_totais(achados), baixou=baixou, subiu=subiu)


def _soma(ws, resumo, achados, colunas, letra):
    """`SUM` na faixa de cada marca e no rodapé, para as duas colunas de total.

    A faixa soma AS LINHAS DELA (é o contrato da planilha de ida: faixa que
    não soma exatamente suas linhas é faixa que discorda das linhas embaixo) e
    o rodapé soma AS FAIXAS — nunca as linhas outra vez, que dobraria o lote.
    """
    from openpyxl.styles import Font
    dados = sorted(a['planilha']['linha'] for a in achados
                   if a['tipo_achado'] == 'linha')
    if not dados:
        return
    faixas = sorted(f['linha'] for f in resumo['faixas'])
    grupos = []
    for i, b in enumerate(faixas):
        fim = faixas[i + 1] if i + 1 < len(faixas) else max(dados) + 1
        meus = [r for r in dados if b < r < fim]
        if meus:
            grupos.append((b, min(meus), max(meus)))

    for c in colunas:
        L = letra(c)
        for b, a0, a1 in grupos:
            cel = ws.cell(b, c, '=SUM(%s%d:%s%d)' % (L, a0, L, a1))
            cel.number_format = FMT_RMB
            cel.font = Font(name=MONO, bold=True, size=10)
        rodape = resumo['total'] and resumo['total']['linha']
        if rodape:
            alvo = ('+'.join('%s%d' % (L, b) for b, _a, _z in grupos)
                    if grupos else 'SUM(%s%d:%s%d)' % (L, min(dados), L,
                                                       max(dados)))
            cel = ws.cell(rodape, c, '=' + alvo)
            cel.number_format = FMT_RMB
            cel.font = Font(name=MONO, bold=True, size=11)


def _totais(achados):
    """``{'antes', 'agora', 'recusa', 'preco'}`` — para o resumo do terminal.

    ANTES é o lote como foi fechado (enviados × ¥ congelado); AGORA é o que a
    planilha propõe (aprovados × ¥ dele). A diferença é a soma de DUAS coisas
    que não podem virar um número só: o que ele RECUSOU (o combinado — chegou
    quebrado, não paga) e o que ele BAIXOU DE PREÇO (renegociação). Juntas
    elas fecham, e é por fechar que a segunda passa batida.
    """
    linhas = [a for a in achados if a['tipo_achado'] == 'linha']
    soma = lambda campo: sum((a[campo] for a in linhas
                              if a.get(campo) is not None), ZERO)
    antes = soma('valor_ov')
    recusa, preco = soma('perda_recusa'), soma('perda_preco')
    return {'antes': antes, 'agora': antes - recusa - preco,
            'recusa': recusa, 'preco': preco}
