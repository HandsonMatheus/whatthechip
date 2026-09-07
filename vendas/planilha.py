# -*- coding: utf-8 -*-
"""
A COMPRA EM PLANILHA — as abas Resumo e Chips, uma em cada aba do arquivo.

Substitui o CSV por aba (dono, 2026-09-02: "o botao de exportar esta
exportando um CSV com os chips, isso nao serve ao comprador"). Dois motivos
para o CSV não servir:

  1. Ele entregava UMA aba — a que estivesse aberta. Quem exporta uma compra
     quer a compra, não o recorte em que o cursor parou.
  2. CSV não tem abas, então "Resumo e Chips" viravam dois downloads que
     ninguém junta depois.

⚠ O CSV também não era fiel à tela: a aba Chips mostra `Tipo` e o CSV não
  exportava essa coluna. Aqui as colunas são as MESMAS da tela, na mesma
  ordem — é o que o dono pediu ("assim EXATAMENTE como elas sao lá no
  sistema"), e é o que torna a planilha conferível contra o que ele viu.

A fonte é o `_detalhe(so)`, o MESMO dicionário que renderiza a ficha. Não é
economia de código: recalcular aqui criaria uma segunda conta para o mesmo
fato, e a primeira vez que as duas divergissem o comprador teria uma planilha
que discorda da tela sem nada que diga qual está certa.

Números saem como NÚMERO, com formato `¥`. Texto formatado ("¥ 1.234,00")
parece igual e não soma — e planilha que não soma é print.
"""

import io

from django.utils.translation import gettext as _, ngettext

# ── A PALETA É A DA TELA ────────────────────────────────────────────────────
# Dono, 2026-09-07: *"é muito comum o comprador exportar os chips e trabalhar
# na planilha, em vez de na UI (...) a ideia é que a planilha seja visualmente
# idêntica à UI, para facilitar a edição e familiaridade lá"*.
#
# Então isto não é "uma planilha bonita": é a MESMA tabela, com os mesmos
# tokens do `static/wtc/tokens/colors.css`, na mesma ordem de colunas. Quem
# muda a cor de uma coluna na tela tem de mudar aqui — há teste comparando os
# rótulos com os `<th>` do template.
INK_90, INK_100 = '21272A', '161616'      # --ink-90 / --ink-100 (cabeçalhos)
INK_10, INK_20, INK_30 = 'F2F4F8', 'DDE1E6', 'C1C7CD'   # faixa, --line, --line-2
INK_70 = '4D5358'
RED_50, RED_10, RED_60 = 'FA4D56', 'FFF1F1', 'DA1E28'
GREEN_40, GREEN_10 = '42BE65', 'E6F7EC'
BLUE_40, BLUE_10 = '78A9FF', 'EDF5FF'
BRANCO = 'FFFFFF'
#: O `{% cycle %}` do quadradinho da faixa de marca, na MESMA ordem do
#: template: a Nª marca da tela recebe a Nª cor, aqui e lá. Na planilha ela
#: vira a borda esquerda grossa da faixa — quadradinho não existe em célula,
#: mas separador por cor sim.
CORES_MARCA = ('0F62FE', '343A3F', '24A148', 'F1C21B', '78A9FF', 'A2A9B0')

#: Manrope e IBM Plex Mono não viajam num .xlsx (o dono já contava com isso:
#: "claro que fontes nao vai rolar"). Consolas é a monoespaçada que o Excel
#: tem nas duas plataformas e é a mais próxima do Plex; Calibri faz o papel da
#: sans. O que importa é a DIVISÃO — número em mono, texto em sans —, que é o
#: que dá à tabela a mesma silhueta da tela.
MONO, SANS = 'Consolas', 'Calibri'

FMT_QTD = '#,##0'
FMT_RMB = '"¥" #,##0.00'
#: rascunho: o mesmo número, com o sinal de estimativa que a tela mostra.
FMT_RMB_EST = '"≈ ¥" #,##0.00'
#: Recusa e perda saem COM O SINAL, como na tela (−14, −¥ 24.00), e o zero
#: fica EM BRANCO — "campo em branco vale zero" é a regra da conferência, e a
#: planilha que o comprador vai preencher tem de dizer a mesma coisa.
FMT_QTD_NEG = '#,##0;"−"#,##0;""'
FMT_RMB_NEG = '"¥" #,##0.00;"−¥" #,##0.00;""'

XLSX = ('application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.sheet')


def _estilos():
    """Os estilos da TELA, traduzidos para célula.

    Cada entrada aqui tem um par no `components.css`; o comentário diz qual,
    porque a fidelidade é o produto: se um dia a tela mudar e isto não, a
    planilha deixa de servir para o que o dono a usa — trabalhar nela em vez
    de na tela.
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    def _b(cor, estilo='thin'):
        return Side(style=estilo, color=cor)

    return {
        # `.dtab th` — mono 10.5, 600, caixa alta, `--ink-90`, texto branco
        'h_fill': PatternFill('solid', fgColor=INK_90),
        'h_font': Font(name=MONO, bold=True, color=BRANCO, size=9),
        'h_alin': Alignment(horizontal='left', vertical='center'),
        # `.dtab th.hr/.hg/.hb` — fundo `--ink-100` e o texto na cor da coluna
        'h_fill_acerto': PatternFill('solid', fgColor=INK_100),
        'h_rej': Font(name=MONO, bold=True, color=RED_50, size=9),
        'h_ace': Font(name=MONO, bold=True, color=GREEN_40, size=9),
        'h_res': Font(name=MONO, bold=True, color=BLUE_40, size=9),
        # `--line` embaixo de cada linha, como o `border-bottom` da tela
        'borda': Border(bottom=_b(INK_20)),
        'texto': Font(name=SANS, size=10),
        'mono': Font(name=MONO, size=10),
        'mono_b': Font(name=MONO, bold=True, size=10),
        # `.dtab .wtc` — a pastilha da caixa, mono menor e cinza
        'wtc': Font(name=MONO, size=9, color=INK_70),
        # `.dtab tbody tr.g td` — faixa da marca: `--ink-10`, negrito,
        # `--line-2` em cima e embaixo
        'g_fill': PatternFill('solid', fgColor=INK_10),
        'g_font': Font(name=SANS, bold=True, size=10),
        'g_mono': Font(name=MONO, bold=True, size=10),
        'g_borda': Border(top=_b(INK_30), bottom=_b(INK_30)),
        # `.dtab tfoot td` — mesma tinta da faixa, mono 600, régua em cima
        't_font': Font(name=MONO, bold=True, size=10),
        't_lbl': Font(name=SANS, bold=True, size=9, color=INK_70),
        't_fill': PatternFill('solid', fgColor=INK_10),
        't_borda': Border(top=_b(INK_30, 'medium')),
        # as três tintas de coluna: `.dtab tbody td.hr/.hg/.hb`
        'f_rej': PatternFill('solid', fgColor=RED_10),
        'f_ace': PatternFill('solid', fgColor=GREEN_10),
        'f_res': PatternFill('solid', fgColor=BLUE_10),
        # O CAMPO. Na tela é um `<input>` branco com régua vermelha dentro da
        # célula rosa; na planilha a célula É o campo, então ela fica branca
        # com a régua vermelha embaixo. Diz "digite aqui" sem precisar de
        # legenda — e é a convenção de marcar célula de entrada.
        'in_fill': PatternFill('solid', fgColor=BRANCO),
        'in_font': Font(name=MONO, bold=True, size=11),
        'in_borda': Border(bottom=_b(RED_60, 'medium'), top=_b(INK_20),
                           left=_b(INK_20), right=_b(INK_20)),
        'perda': Font(name=MONO, size=10, color=RED_60),
        'dir': Alignment(horizontal='right', vertical='center'),
        'esq': Alignment(horizontal='left', vertical='center'),
    }


def _colunas(ws, colunas, e, linha):
    """A barra preta dos títulos — a `<thead>` da tela."""
    from openpyxl.utils import get_column_letter
    for i, coluna in enumerate(colunas, start=1):
        rotulo, largura, tinta = coluna
        c = ws.cell(row=linha, column=i, value=rotulo)
        c.fill = e['h_fill_acerto'] if tinta else e['h_fill']
        c.font = {'rej': e['h_rej'], 'ace': e['h_ace'],
                  'res': e['h_res']}.get(tinta, e['h_font'])
        c.alignment = e['h_alin']
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[linha].height = 30


def _impressao(ws, titulos):
    """A tabela é larga e ele imprime: sem isto o Excel quebra as colunas do
    acerto para uma segunda folha, e a conferência chega ao papel partida ao
    meio — que é o oposto de "igual à tela"."""
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.print_title_rows = titulos


def _titulo(ws, so, colunas, e):
    """O cabeçalho SIMPLES da aba Chips: uma linha de identificação."""
    from openpyxl.styles import Font
    ws.cell(row=1, column=1, value='%s · %s · %s' % (
        so.code, so.company.name if so.company_id else '—',
        so.lot.get_origin_display() if so.lot_id else '—')).font = Font(
            name=SANS, bold=True, size=12)
    ws.freeze_panes = 'A4'
    _impressao(ws, '1:3')
    _colunas(ws, colunas, e, 3)


def _dica(ws, texto, e):
    """A barra azul do `.rhint`, na linha logo acima da tabela."""
    from openpyxl.styles import Alignment, Font, PatternFill
    for col in range(1, _COLS + 1):
        ws.cell(row=LINHA_CAB - 1, column=col).fill = PatternFill(
            'solid', fgColor=BLUE_10)
    c = ws.cell(row=LINHA_CAB - 1, column=1, value=texto)
    c.font = Font(name=SANS, size=9, color=INK_70)
    c.alignment = Alignment(vertical='center')
    ws.row_dimensions[LINHA_CAB - 1].height = 20


def _cabecalho_da_compra(ws, so, ctx, e, acerto, ultima_linha):
    """O TOPO INFORMATIVO do Resumo (dono, 2026-09-07).

      "faca um cabecalho informativo simples com o valor esperado e o valor do
       resultado, esse deve se atualizar conforme ele vai mexendo, deve ter tbm
       nesse cabeclho o numero da ordem de venda, o TIPO do lote, o cliente e a
       TAXA de cambio, essas sao as unicas informacoes q importam, nome do
       comprador e numero de lote remova."

    É o herói da ficha, em célula: as três identificações à esquerda e os dois
    números grandes à direita, cada um com ¥ em cima e US$ embaixo — a mesma
    pilha da tela.

    ⚠ SAÍRAM o nome do comprador e o código do lote. O arquivo continua se
      identificando pelo CÓDIGO DA ORDEM, que é a chave que ele cita e a que a
      importação vai conferir.

    ⚠ O RESULTADO É FÓRMULA; o esperado é valor. O esperado é o congelado da
      ordem — o número que o cliente tinha na mão quando a caixa saiu — e não
      se move enquanto ele digita. O resultado se move: é ele que responde
      "quanto sobrou".

    ⚠ Cada número ocupa DUAS colunas (`merge`). A primeira versão punha um por
      coluna e o Excel devolveu `###` em todos os quatro: 13pt em mono não
      cabe em 13 caracteres. Foi o arquivo aberto que disse isso, não a
      leitura do código.
    """
    from openpyxl.styles import Alignment, Border, Font, Side
    fx = so.fx_usd_rate
    AZUL_HERO = '0F62FE'

    ws.cell(row=1, column=1, value=so.code).font = Font(
        name=SANS, bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 6

    def _campo(col, rotulo, valor, fmt=None):
        r = ws.cell(row=3, column=col, value=rotulo)
        r.font, r.alignment = e['t_lbl'], e['esq']
        v = ws.cell(row=4, column=col, value=valor)
        v.font, v.alignment = e['mono_b'], e['esq']
        if fmt:
            v.number_format = fmt
        for f in (3, 4):
            ws.merge_cells(start_row=f, start_column=col,
                           end_row=f, end_column=col + 1)

    _campo(CAB_CLIENTE, _('Cliente').upper(),
           so.company.name if so.company_id else '—')
    _campo(CAB_LOTE, _('Tipo do lote').upper(),
           so.lot.get_origin_display() if so.lot_id else '—')
    _campo(CAB_TAXA, _('Taxa').upper() + ' ¥→US$',
           float(fx) if fx else '—', fmt='0.0000' if fx else None)

    # ── OS DOIS NÚMEROS, ¥ em cima e US$ embaixo, como na tela ────────────
    def _hero(col, rotulo, rmb, usd, fmt_rmb, azul):
        cor = AZUL_HERO if azul else '161616'
        r = ws.cell(row=3, column=col, value=rotulo)
        r.font = Font(name=SANS, bold=True, size=9,
                      color=AZUL_HERO if azul else INK_70)
        r.alignment = e['esq']
        for linha, valor, fmt in ((4, rmb, fmt_rmb),
                                  (5, usd, '"US$" #,##0.00')):
            c = ws.cell(row=linha, column=col, value=valor)
            c.font = Font(name=MONO, bold=True, size=12, color=cor)
            c.alignment, c.number_format = e['esq'], fmt
        for linha in (3, 4, 5):
            ws.merge_cells(start_row=linha, start_column=col,
                           end_row=linha, end_column=col + 1)

    esperado_rmb = (float(ctx['total_estimado']) if ctx['estimado']
                    else (float(so.total_rmb) if so.total_rmb else '—'))
    fmt_esp = FMT_RMB_EST if ctx['estimado'] else FMT_RMB
    _hero(CAB_ESP, _('Resultado esperado').upper(), esperado_rmb,
          float(so.total_usd) if so.total_usd else '—', fmt_esp, False)
    if acerto:
        # O ¥ vem do rodapé; o US$ vem da coluna escondida — `SUMPRODUCT` de
        # aprovados × unitário congelado. As faixas entram no intervalo e
        # contribuem ZERO, porque a coluna do US$ é vazia nelas.
        #
        # ⚠ Sem NENHUM unitário em US$ (ordem legada, rascunho sem taxa) o
        #   `SUMPRODUCT` daria zero, e "US$ 0.00" é um preço — ausência de
        #   preço não é. Aí sai travessão, como a tela faz.
        tem_usd = any(l['unit_usd'] is not None
                      for g in ctx['grupos'] for l in g['lines'])
        _hero(CAB_RES, _('Resultado').upper(),
              '=%s%d' % (_L(COL_RES), ultima_linha),
              '=SUMPRODUCT(%s%d:%s%d,%s%d:%s%d)' % (
                  _L(COL_ACE), LINHA_1, _L(COL_ACE), ultima_linha - 1,
                  _L(COL_USD), LINHA_1, _L(COL_USD), ultima_linha - 1)
              if tem_usd else '—',
              FMT_RMB, True)
    else:
        _hero(CAB_RES, _('Resultado').upper(), esperado_rmb,
              float(so.total_usd) if so.total_usd else '—', fmt_esp, True)
    ws.row_dimensions[3].height = 14
    for linha in (4, 5):
        ws.row_dimensions[linha].height = 20

    # a régua azul que fecha o cabeçalho, como na ficha
    for col in range(1, _COLS + 1):
        ws.cell(row=5, column=col).border = Border(
            bottom=Side(style='medium', color=AZUL_HERO))


def _pinta(ws, linha, dados, e, fonte=None, fill=None, borda=None):
    from openpyxl.styles import Alignment
    for i, valor in enumerate(dados, start=1):
        c = ws.cell(row=linha, column=i, value=valor)
        c.border = borda if borda is not None else e['borda']
        c.alignment = Alignment(vertical='center')
        if fonte is not None:
            c.font = fonte
        if fill is not None:
            c.fill = fill
    return ws[linha]


def _num(ws, linha, coluna, formato):
    ws.cell(row=linha, column=coluna).number_format = formato


def _dinheiro(valor, legado):
    """O que a CÉLULA recebe quando não há preço.

    A tela escreve "sem preço" no unitário e "—" no total, e a planilha diz o
    mesmo: um vazio aqui seria lido como zero, que é a única leitura errada
    possível — zero é um preço, ausência de preço não é.
    """
    if valor is not None:
        return float(valor)
    return '—' if legado else _('sem preço')


# ── ABA RESUMO ───────────────────────────────────────────────────────────
#: As colunas SÃO as `<th>` da tabela do Resumo, na MESMA ordem
#: (dono, 2026-09-07: "iguais em termos não só de design, como também de uso e
#: posicionamento de cada coluna"). Duas consequências que valem dizer:
#:
#:   · A MARCA SAIU DE COLUNA. Na tela ela é a faixa de grupo, e aqui passou a
#:     ser também — uma coluna a mais deslocaria todas as outras, que é
#:     exatamente o que "posicionamento" proíbe. Quem precisar filtrar por
#:     marca tem a aba Chips, que tem a coluna.
#:   · O DINHEIRO SAI EM ¥. Na tela cada coluna de dinheiro mostra o par
#:     US$/¥ empilhado; numa célula isso seria texto, e texto não soma. Uma
#:     coluna por coluna da tela, em ¥, com a moeda no rótulo.
_COLS = 10
#: ⚠ ORDEM revista pelo dono em 2026-09-07 ("mover ESPERADO para o lado
#:   esquerdo de RESULTADO" / "trocar ENVIADOS e UNITARIO de lugar"). Ela vale
#:   AQUI E NA TELA — as duas mudaram juntas, que é o ponto de a planilha ser
#:   a tela em célula.
#:
#:   UNITÁRIO · ENVIADOS · RECUSADOS · RECUSADOS ¥ · APROVADOS · ESPERADO ·
#:   RESULTADO
#:
#:   O preço vem antes da quantidade (ele confere o preço primeiro, depois
#:   quanto veio), e ESPERADO cola em RESULTADO: os dois números que ele
#:   compara ficam vizinhos, sem o olho atravessar a tabela.
COL_TIPO, COL_CAP, COL_WTC, COL_UNIT, COL_ENV = 1, 2, 3, 4, 5
COL_REJ, COL_REJV, COL_ACE, COL_ESP, COL_RES = 6, 7, 8, 9, 10
#: SEM conferência não existem RECUSADOS/APROVADOS/RESULTADO — e o ESPERADO
#: na 9 deixaria três colunas vazias no meio da tabela. Aí ele fecha na 6,
#: como última coluna. É a mesma regra da tela, que também não desenha as
#: quatro colunas antes do recebimento.
COL_ESP_SEM_ACERTO = 6
#: A primeira coluna NUMÉRICA: daqui para a direita é mono e alinhado à
#: direita. Nomeada porque a ordem já mudou duas vezes e `col >= COL_ENV`
#: virava mentira silenciosa a cada troca.
#: ⚠ COLUNA ESCONDIDA, depois de todas as visíveis. Guarda o US$ unitário
#:   CONGELADO de cada linha, e existe por um motivo só: o cabeçalho mostra o
#:   resultado nas duas moedas, e o US$ da tela NÃO é ¥ × taxa — é a soma dos
#:   unitários congelados. Derivar da taxa daria um número que discorda da
#:   tela em alguns dólares, que é a divergência silenciosa que este projeto
#:   passa a vida caçando. Fica em K (depois de tudo) para não deslocar
#:   coluna nenhuma, e escondida porque é insumo, não leitura.
COL_NUM1 = COL_UNIT
COL_USD = 11

#: ⚠ O CABEÇALHO tem o layout DELE, e de propósito não reaproveita as
#:   constantes da tabela: os cinco blocos do topo (três campos + dois
#:   números, duas colunas cada) não têm nada a ver com a ordem das colunas de
#:   dados, e quando tinham, trocar a ordem da tabela embaralhava o cabeçalho
#:   junto — foi o que quase aconteceu na revisão de 07/09.
CAB_CLIENTE, CAB_LOTE, CAB_TAXA, CAB_ESP, CAB_RES = 1, 3, 5, 7, 9

#: A tabela começa mais abaixo desde 2026-09-07: o cabeçalho informativo
#: ocupa as cinco primeiras linhas e a dica a sexta.
LINHA_CAB, LINHA_1 = 7, 8

#: `{coluna: chave de tinta}` — as mesmas `.hr/.hg/.hb` da tela.
TINTA = {COL_REJ: 'rej', COL_REJV: 'rej', COL_ACE: 'ace', COL_RES: 'res'}


def _L(col):
    from openpyxl.utils import get_column_letter
    return get_column_letter(col)


def _aba_resumo(ws, so, ctx):
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.styles import Border, Side

    e = _estilos()
    ws.title = _('Resumo')
    acerto = ctx['pode_acertar'] or ctx['tem_resultado']
    editavel = ctx['pode_acertar']
    legado = ctx['registro_legado']

    # O ESPERADO fecha a tabela quando não há conferência, e cola no
    # RESULTADO quando há — as duas ordens da tela, sem coluna vazia.
    esperado = ('%s ¥' % _('Esperado').upper(), 15, None)
    colunas = [(_('Tipo').upper(), 15, None),
               (_('Capacidade').upper(), 15, None),
               (_('Caixa WTC').upper(), 14, None),
               ('%s ¥' % _('Unitário').upper(), 13, None),
               (_('Enviados').upper(), 12, None)]
    if acerto:
        colunas += [(_('Recusados').upper(), 13, 'rej'),
                    ('%s ¥' % _('Recusados').upper(), 15, 'rej'),
                    (_('Aprovados').upper(), 13, 'ace'),
                    esperado,
                    ('%s ¥' % _('Resultado').upper(), 15, 'res')]
    else:
        colunas += [esperado]

    r = LINHA_1
    faixas, campos = [], []
    for i, g in enumerate(ctx['grupos']):
        faixa_r, r = r, r + 1
        primeira = r
        for l in g['lines']:
            _linha_do_chip(ws, r, l, e, acerto, editavel, legado, ctx)
            if editavel:
                campos.append(r)
            r += 1
        _faixa_da_marca(ws, faixa_r, g, i, e, acerto, legado, ctx,
                        primeira, r - 1, CellRichText, TextBlock, InlineFont,
                        Border, Side)
        faixas.append(faixa_r)

    _rodape(ws, r, ctx, so, e, acerto, legado, faixas)
    _cabecalho_da_compra(ws, so, ctx, e, acerto, r)
    if editavel:
        # A MESMA frase da barra azul da tela (`.rhint`) — ele reconhece a
        # regra do campo antes de digitar a primeira célula, e quem abrir o
        # arquivo dias depois a lê sem precisar perguntar.
        _dica(ws, _('Digite só o que recusou — campo em branco vale zero.'),
              e)
    _colunas(ws, colunas, e, LINHA_CAB)
    if acerto:
        # A coluna escondida do US$ unitário — insumo do cabeçalho, não
        # leitura. Nem título tem: um `<th>` ali seria uma coluna a mais.
        ws.column_dimensions[_L(COL_USD)].hidden = True
    ws.freeze_panes = '%s%d' % (_L(1), LINHA_1)
    _impressao(ws, '1:%d' % LINHA_CAB)
    if editavel:
        _so_o_campo_e_editavel(ws, campos, r)


def _so_o_campo_e_editavel(ws, campos, ultima):
    """A planilha inteira TRANCADA, menos a coluna que ele digita.

    Dono, 2026-09-07: *"esta sendo possivel digital texto tbm onde digita os
    chips rechazados, proiba"* e *"inabilite todos os outros campos de serem
    editados, exceto o de chips recusados"*.

    Duas travas, e elas respondem a coisas diferentes:

      · A PROTEÇÃO da folha impede tocar em qualquer célula que não seja o
        campo. Sem ela, um Ctrl+V no lugar errado apaga uma fórmula e a
        planilha passa a mostrar um número que não é dela — em silêncio.
      · A VALIDAÇÃO recusa o que não é inteiro entre 0 e o enviado. É o
        `min`/`max` do `<input>` da tela, palavra por palavra: recusar 20 de
        13 não é digitação, é engano, e a tela sempre barrou.

    ⚠ SEM SENHA, de propósito. Isto é guarda de mão trocada, não segredo:
      qualquer um remove a proteção em dois cliques, e é assim que tem de ser
      — uma planilha que ele não consegue destrancar viraria um problema
      dele, não uma ajuda.

    Redimensionar coluna e linha continua liberado: não é editar dado, e uma
    coluna estreita demais que não se pode alargar é uma tela pior.
    """
    from openpyxl.styles import Protection
    from openpyxl.worksheet.datavalidation import DataValidation

    for linha in ws.iter_rows(min_row=1, max_row=ultima, max_col=COL_USD):
        for c in linha:
            c.protection = Protection(locked=True)
    for r in campos:
        ws.cell(row=r, column=COL_REJ).protection = Protection(locked=False)

    ws.protection.sheet = True
    ws.protection.formatColumns = False      # False = PERMITIDO
    ws.protection.formatRows = False
    ws.protection.selectLockedCells = False  # ler e copiar continua livre
    ws.protection.selectUnlockedCells = False

    if not campos:
        return
    # ⚠ UMA validação para todos os campos, com `formula2` RELATIVA. O Excel
    #   ancora a referência na primeira célula do `sqref` e desloca por
    #   célula. `$D8` trava a COLUNA e deixa a linha correr: em `G12` a regra
    #   vira `$D12`, em `G27` vira `$D27` — inclusive com as faixas no meio,
    #   porque o deslocamento é por linha. O `$` não é enfeite: sem ele a
    #   referência anda também na horizontal se alguém mexer no `sqref`.
    #   Uma validação por linha daria o mesmo e um arquivo bem maior.
    dv = DataValidation(
        type='whole', operator='between',
        formula1='0', formula2='$%s%d' % (_L(COL_ENV), campos[0]),
        allow_blank=True, showErrorMessage=True, errorStyle='stop',
        errorTitle=_('Quantidade inválida'),
        error=_('Digite um número inteiro entre 0 e a quantidade enviada.'))
    ws.add_data_validation(dv)
    for r in campos:
        dv.add(ws.cell(row=r, column=COL_REJ))


def _linha_do_chip(ws, r, l, e, acerto, editavel, legado, ctx):
    """Uma categoria — a `<tr>` de dados da tela, célula por célula."""
    fmt_unit = FMT_RMB_EST if ctx['estimado'] else FMT_RMB
    esp = COL_ESP if acerto else COL_ESP_SEM_ACERTO
    esperado = (float(l['total_rmb']) if l['total_rmb'] is not None else '—')
    base = [l['type'], l['capacity'], l['wtc'],
            _dinheiro(l['unit_rmb'], legado), l['qty']]
    # Com conferência o ESPERADO é a 9ª (três colunas de acerto na frente e o
    # RESULTADO, fórmula, escrito depois); sem ela, é a 6ª e última.
    _pinta(ws, r, base + ([None, None, None, esperado, None] if acerto
                          else [esperado]), e)
    ws.cell(row=r, column=COL_TIPO).font = e['texto']
    ws.cell(row=r, column=COL_CAP).font = e['mono_b']
    ws.cell(row=r, column=COL_WTC).font = e['wtc']
    for col in (COL_UNIT, COL_ENV, esp):
        ws.cell(row=r, column=col).font = e['mono']
        ws.cell(row=r, column=col).alignment = e['dir']
    _num(ws, r, COL_ENV, FMT_QTD)
    if l['unit_rmb'] is not None:
        _num(ws, r, COL_UNIT, fmt_unit)
    if l['total_rmb'] is not None:
        _num(ws, r, esp, FMT_RMB)
    ws.row_dimensions[r].height = 22
    if not acerto:
        return

    # ── AS QUATRO COLUNAS DA CONFERÊNCIA ──────────────────────────────────
    # ⚠ FÓRMULA, e não o número que o servidor calculou. É a diferença entre
    #   uma foto e a tela: o dono trabalha NA planilha, e digitar 12 aqui tem
    #   de mover a perda, o aprovado, o resultado, a faixa da marca e o
    #   rodapé — que é o que acontece quando ele digita na tela. Uma planilha
    #   que não recalcula obriga a conferir tudo de novo lá.
    for col in (COL_REJ, COL_REJV, COL_ACE, COL_RES):
        c = ws.cell(row=r, column=col)
        c.fill = {'rej': e['f_rej'], 'ace': e['f_ace'],
                  'res': e['f_res']}[TINTA[col]]
        c.font = e['mono']
        c.alignment = e['dir']

    rej = ws.cell(row=r, column=COL_REJ)
    if editavel:
        # A CÉLULA DE ENTRADA. Vazia: "campo em branco vale zero", igual à
        # tela. Branca com régua vermelha embaixo, que é o `<input>` do
        # design system — é por ela que o comprador anda, e é ela que a
        # importação vai ler.
        rej.value = l['rejected'] or None
        rej.fill, rej.font, rej.border = (e['in_fill'], e['in_font'],
                                          e['in_borda'])
    else:
        rej.value = -l['rejected'] if l['rejected'] else None
    _num(ws, r, COL_REJ, FMT_QTD if editavel else FMT_QTD_NEG)

    u, env = '%s%d' % (_L(COL_UNIT), r), '%s%d' % (_L(COL_ENV), r)
    q = '%s%d' % (_L(COL_REJ), r)
    ace = '%s%d' % (_L(COL_ACE), r)
    # ⚠ `N()` devolve ZERO para vazio e para texto. É o que faz "campo em
    #   branco vale zero" valer também na planilha, sem um `IFERROR` em cada
    #   linha — e é o que impede a coluna inteira de virar `#VALUE!` quando o
    #   comprador digitar "ok" numa célula por engano.
    #
    # Em conferência ele digita POSITIVO (é o que a tela mostra no campo);
    # fechada, a célula já vem negativa, como a tela mostra ali. Daí os dois
    # sinais — não é gosto, é o número que está na célula.
    ws.cell(row=r, column=COL_REJV).value = (
        '=IF(ISNUMBER(%s),%sN(%s)*%s,"")'
        % (u, '-' if editavel else '', q, u))
    ws.cell(row=r, column=COL_ACE).value = (
        '=%s-N(%s)' % (env, q) if editavel else '=%s+N(%s)' % (env, q))
    ws.cell(row=r, column=COL_RES).value = (
        '=IF(ISNUMBER(%s),%s*%s,"—")' % (u, ace, u))
    _num(ws, r, COL_REJV, FMT_RMB_NEG)
    _num(ws, r, COL_ACE, FMT_QTD)
    _num(ws, r, COL_RES, FMT_RMB)
    # O insumo ESCONDIDO do US$ do cabeçalho: o unitário CONGELADO da
    # linha, que é de onde a tela tira o dólar — e não de ¥ × taxa.
    if l['unit_usd'] is not None:
        ws.cell(row=r, column=COL_USD, value=float(l['unit_usd']))


def _faixa_da_marca(ws, r, g, i, e, acerto, legado, ctx, a, b,
                    CellRichText, TextBlock, InlineFont, Border, Side):
    """A `<tr class="g">` da tela: a marca, quantas linhas, e os subtotais.

    Vem DEPOIS das linhas dela no código (e antes no arquivo) porque os
    subtotais são `SUM` do intervalo — o mesmo contrato da tela, onde a faixa
    tem de somar exatamente as linhas dela.
    """
    from openpyxl.styles import Alignment, PatternFill
    n = len(g['lines'])
    ws.merge_cells(start_row=r, start_column=COL_TIPO,
                   end_row=r, end_column=COL_WTC)
    c = ws.cell(row=r, column=COL_TIPO)
    c.value = CellRichText(
        TextBlock(InlineFont(rFont=SANS, b=True, sz=10), g['brand']),
        TextBlock(InlineFont(rFont=SANS, sz=8, color=INK_70),
                  '   ' + ngettext('%(n)s linha', '%(n)s linhas', n)
                  % {'n': n}))
    c.alignment = Alignment(vertical='center')
    # O quadradinho de cor da tela vira a régua esquerda da faixa: a Nª marca
    # recebe a Nª cor, aqui e lá.
    cor = CORES_MARCA[i % len(CORES_MARCA)]
    esp = COL_ESP if acerto else COL_ESP_SEM_ACERTO
    for col in range(1, (_COLS if acerto else COL_ESP_SEM_ACERTO) + 1):
        cel = ws.cell(row=r, column=col)
        cel.fill = e['g_fill']
        cel.border = e['g_borda']
        cel.font = e['g_mono'] if col >= COL_NUM1 else e['g_font']
        if col >= COL_NUM1:
            cel.alignment = e['dir']
    ws.cell(row=r, column=COL_TIPO).border = Border(
        left=Side(style='thick', color=cor), top=e['g_borda'].top,
        bottom=e['g_borda'].bottom)
    ws.row_dimensions[r].height = 24

    def soma(col):
        L = _L(col)
        return '=SUM(%s%d:%s%d)' % (L, a, L, b)

    ws.cell(row=r, column=COL_ENV).value = soma(COL_ENV)
    _num(ws, r, COL_ENV, FMT_QTD)
    if legado:
        ws.cell(row=r, column=esp).value = '—'
    else:
        ws.cell(row=r, column=esp).value = soma(esp)
        _num(ws, r, esp, FMT_RMB)
    if not acerto:
        return
    # Na faixa a recusa é NEGATIVA, como na tela (−14): ali ela não é campo,
    # é consequência.
    L = _L(COL_REJ)
    ws.cell(row=r, column=COL_REJ).value = (
        '=-SUM(%s%d:%s%d)' % (L, a, L, b) if ctx['pode_acertar']
        else soma(COL_REJ))
    ws.cell(row=r, column=COL_REJV).value = soma(COL_REJV)
    ws.cell(row=r, column=COL_ACE).value = soma(COL_ACE)
    ws.cell(row=r, column=COL_RES).value = soma(COL_RES)
    _num(ws, r, COL_REJ, FMT_QTD_NEG)
    _num(ws, r, COL_REJV, FMT_RMB_NEG)
    _num(ws, r, COL_ACE, FMT_QTD)
    _num(ws, r, COL_RES, FMT_RMB)
    ws.cell(row=r, column=COL_REJV).font = e['perda']


def _rodape(ws, r, ctx, so, e, acerto, legado, faixas):
    """O `<tfoot>` da tela: "Total · N marcas" e a soma de cada coluna.

    Soma as FAIXAS, não as linhas: cada faixa já soma as linhas dela, então o
    rodapé fecha com a tela por construção, e a conta é a mesma cadeia que a
    tela usa (linha → grupo → total).
    """
    from openpyxl.styles import Alignment
    n = len(ctx['grupos'])
    ws.cell(row=r, column=COL_TIPO, value=ngettext(
        'Total · %(n)s marca', 'Total · %(n)s marcas', n) % {'n': n})
    ws.merge_cells(start_row=r, start_column=COL_TIPO,
                   end_row=r, end_column=COL_WTC)
    esp = COL_ESP if acerto else COL_ESP_SEM_ACERTO
    for col in range(1, (_COLS if acerto else COL_ESP_SEM_ACERTO) + 1):
        c = ws.cell(row=r, column=col)
        c.fill = {'rej': e['f_rej'], 'ace': e['f_ace'],
                  'res': e['f_res']}.get(TINTA.get(col)) or e['t_fill']
        c.font = e['t_font'] if col >= COL_NUM1 else e['t_lbl']
        c.border = e['t_borda']
        c.alignment = e['dir'] if col >= COL_NUM1 else Alignment(
            horizontal='left', vertical='center')
    ws.row_dimensions[r].height = 26

    def soma(col):
        L = _L(col)
        return '=' + '+'.join('%s%d' % (L, f) for f in faixas) if faixas \
            else None

    ws.cell(row=r, column=COL_ENV).value = soma(COL_ENV)
    _num(ws, r, COL_ENV, FMT_QTD)
    # ⚠ O esperado do rodapé é o CONGELADO da ordem, não a soma das faixas —
    #   é o número que o cliente tinha na mão quando a caixa saiu, e é o que a
    #   tela mostra ali. No rascunho não há congelado: aí é a soma viva, com o
    #   "≈" que a tela também põe.
    if ctx['estimado']:
        ws.cell(row=r, column=esp).value = float(ctx['total_estimado'])
    elif so.total_rmb:
        ws.cell(row=r, column=esp).value = float(so.total_rmb)
    else:
        ws.cell(row=r, column=esp).value = '—'
    _num(ws, r, esp, FMT_RMB_EST if ctx['estimado'] else FMT_RMB)
    if not acerto:
        return
    for col in (COL_REJ, COL_REJV, COL_ACE, COL_RES):
        ws.cell(row=r, column=col).value = soma(col)
    _num(ws, r, COL_REJ, FMT_QTD_NEG)
    _num(ws, r, COL_REJV, FMT_RMB_NEG)
    _num(ws, r, COL_ACE, FMT_QTD)
    _num(ws, r, COL_RES, FMT_RMB)
    ws.cell(row=r, column=COL_REJV).font = e['perda']


# ── ABA CHIPS ────────────────────────────────────────────────────────────
def _aba_chips(ws, so, ctx):
    e = _estilos()
    ws.title = _('Chips')
    legado = ctx['registro_legado']
    chips = ctx['chips']

    # As colunas da aba Chips da tela, na ordem — só o desenho mudou
    # (cabeçalho preto, mono em caixa alta), para as duas abas do arquivo
    # pertencerem ao mesmo produto.
    colunas = [(_('Part Number').upper(), 24, None), (_('Marca').upper(), 16, None),
               (_('Tipo').upper(), 14, None), (_('Spec').upper(), 20, None),
               (_('Caixa WTC').upper(), 14, None), (_('Qtd.').upper(), 11, None),
               ('%s ¥' % _('Unitário').upper(), 13, None),
               ('%s ¥' % _('Total').upper(), 15, None)]
    _titulo(ws, so, colunas, e)

    r = 4
    for c in chips['linhas']:
        _pinta(ws, r, [c['pn'], c['brand'], c['type'], c['spec'], c['wtc'],
                       c['qty'], _dinheiro(c['unit_rmb'], legado),
                       float(c['total_rmb']) if c['total_rmb'] is not None
                       else '—'], e)
        ws.cell(row=r, column=1).font = e['mono']     # PN é código, não texto
        _num(ws, r, 6, FMT_QTD)
        if c['unit_rmb'] is not None:
            _num(ws, r, 7, FMT_RMB)
        if c['total_rmb'] is not None:
            _num(ws, r, 8, FMT_RMB)
        r += 1

    _pinta(ws, r, [_('Total'), '', '', '', '', chips['qty'], '',
                   '—' if legado else float(chips['rmb'])],
           e, fonte=e['t_font'], borda=e['t_borda'])
    _num(ws, r, 6, FMT_QTD)
    if not legado:
        _num(ws, r, 8, FMT_RMB)


# ── A ENTRADA ────────────────────────────────────────────────────────────
def compra_em_planilha(so, ctx):
    """Devolve ``(bytes, nome_do_arquivo)``.

    `ctx` é o `_detalhe(so)` da ficha — quem chama passa o MESMO dicionário
    que a tela usou, e não um recalculado.
    """
    from openpyxl import Workbook
    wb = Workbook()
    _aba_resumo(wb.active, so, ctx)
    _aba_chips(wb.create_sheet(), so, ctx)
    wb.properties.creator = 'WhatTheChip?'
    wb.properties.title = so.code

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # O nome leva o código da ORDEM, e não o do lote como fazia o CSV. O
    # código do lote perdeu o prefixo da empresa em 2026-09-02: dois clientes
    # com o lote 7 dariam o MESMO nome de arquivo na pasta de Downloads. É a
    # mesma colisão que tirou a coluna do lote da lista de compras.
    return buf.read(), '%s.xlsx' % so.code.replace('/', '-')
