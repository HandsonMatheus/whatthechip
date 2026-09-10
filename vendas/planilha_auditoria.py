# -*- coding: utf-8 -*-
"""
planilha_auditoria.py — LER de volta a planilha que o comprador editou.

O caminho de ida existe desde 2026-09-02 (`vendas/planilha.py`): o sistema
exporta a compra em duas abas e o comprador trabalha nela em vez da tela
("é muito comum o comprador exportar os chips e trabalhar na planilha").
Este módulo é o caminho de VOLTA — o arquivo que ele devolve, mexido, virando
diferença conferível contra o que a Ordem de Venda congelou.

⚠ POR QUE UM PARSER TOLERANTE, E NÃO O INVERSO DO `planilha.py`.
  A planilha que volta NÃO é a que saiu. Três coisas acontecem com ela no
  caminho, e todas já aconteceram no arquivo real de EMIN-SO-2026-0004:

    1. Ele abre em OUTRA ferramenta (o arquivo veio "Copy of …", grafia do
       Google Sheets). Fórmula vira número cravado, proteção de folha some,
       validação some. Nada disso é recuperável na volta — só o VALOR é.
    2. O arquivo é de uma VERSÃO ANTERIOR do export. O de 12/09 tem coluna
       `Marca` em toda linha e não tem `¥ RECUSADOS` (que nasceu em 07/09).
       Um parser posicional leria a coluna errada com convicção.
    3. Ele ACRESCENTA coluna. O check de "mexi aqui" mora numa coluna que o
       sistema nunca escreveu — e é justamente ela que dá a intenção dele.

  Então o parser casa por CABEÇALHO, normalizado e por radical, nos quatro
  idiomas da casa (I18N.md), e trata qualquer coluna não reconhecida como
  possível marca do comprador. Posição de coluna aqui é palpite; nome não.

NÃO TOCA NO BANCO. Este módulo é PURO: entra arquivo, sai estrutura. Quem
lê o banco é o `auditar_planilha_comprador`, e é lá que mora o escopo do RLS.
"""

from decimal import Decimal, InvalidOperation
import re
import unicodedata


# ── NORMALIZAÇÃO ────────────────────────────────────────────────────────────
def _sem_acento(txt: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', txt)
                   if unicodedata.category(c) != 'Mn')


def normaliza(v) -> str:
    """Chave de comparação de TEXTO: sem acento, sem caixa, sem espaço duplo.

    Serve para cabeçalho e também para casar marca/tipo/caixa da planilha com
    os do banco — 'SK Hynix' e 'SK  HYNIX' são a mesma marca, e a planilha
    passou por um editor que reescreve espaço."""
    if v is None:
        return ''
    return ' '.join(_sem_acento(str(v)).strip().lower().split())


#: Radical → papel da coluna. Casado por SUBSTRING no cabeçalho normalizado,
#: nesta ordem — o primeiro que casar vence. A ordem importa: 'unit' aparece
#: dentro de 'unitario' e de '¥ unit.', e nenhum outro papel contém o radical
#: de outro. Os quatro idiomas de `locale/` (pt-br, es, en, zh-hans).
_RADICAIS = [
    ('pn',         ('part number', 'part-number', 'pn', '料号', '型号')),
    ('marca',      ('marca', 'brand', '品牌')),
    ('tipo',       ('tipo', 'type', '类型')),
    ('spec',       ('spec',)),
    ('capacidade', ('capacid', 'capacity', '容量')),
    ('caixa',      ('caixa', 'caja', 'wtc', 'box', '箱')),
    ('unit',       ('unitario', 'unit', '单价')),
    ('enviados',   ('enviad', 'sent', 'shipped', '发出', '发货')),
    ('recusados',  ('recusad', 'rechazad', 'reject', '拒收')),
    ('aprovados',  ('aprovad', 'aprobad', 'approv', '核对', '接受')),
    ('esperado',   ('esperad', 'expected', '预期')),
    ('resultado',  ('resultad', 'result', '结算', '结果')),
    ('total',      ('total', '合计', '总计')),
    ('qtd',        ('cant', 'qtd', 'qty', 'quantid', '数量')),
]

#: Papéis que são DINHEIRO por definição — o ¥ no cabeçalho é decoração.
_DINHEIRO = {'unit', 'esperado', 'resultado', 'total'}


def papel_da_coluna(bruto):
    """``('recusados', True)`` = a coluna ¥ RECUSADOS; ``(..., False)`` = a de
    quantidade. ``(None, False)`` = coluna que o sistema não escreveu.

    O ¥ decide entre as DUAS colunas de recusa (a de peça e a de dinheiro,
    2026-09-07) e é ignorado nas demais: '¥ unit.' e 'UNITÁRIO ¥' são a mesma
    coluna escrita por duas versões do export."""
    txt = normaliza(bruto)
    if not txt:
        return None, False
    moeda = ('¥' in str(bruto)) or ('rmb' in txt) or ('cny' in txt)
    for papel, radicais in _RADICAIS:
        if any(rad in txt for rad in radicais):
            return papel, (moeda and papel not in _DINHEIRO)
    return None, False


def numero(v):
    """Decimal ou None. Texto de planilha editada em outra ferramenta chega
    como '1.234,00', '¥ 12', '—' ou string vazia — nada disso é número, e
    inventar zero aqui viraria 'ele zerou o preço'."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    txt = str(v).strip().replace('¥', '').replace('$', '').replace(' ', '')
    txt = txt.replace(' ', '')
    if not txt or txt in {'—', '-', '–', 'None'}:
        return None
    # 1.234,56 (pt/es) → 1234.56 · 1,234.56 (en) → 1234.56
    if ',' in txt and '.' in txt:
        txt = (txt.replace('.', '').replace(',', '.')
               if txt.rindex(',') > txt.rindex('.') else txt.replace(',', ''))
    elif ',' in txt:
        txt = txt.replace(',', '.')
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


# ── ONDE COMEÇA A TABELA ────────────────────────────────────────────────────
#: Quantos papéis distintos uma linha precisa ter para ser o CABEÇALHO. Três
#: é baixo de propósito: a aba Chips de um export antigo tem 8 colunas e a
#: Resumo pode ter 6, e o A1 (título da compra) nunca tem mais de um.
_MIN_PAPEIS = 3


def mapa_de_colunas(ws, limite=20):
    """``(linha_do_cabecalho, {papel: coluna}, [colunas_estranhas])``.

    As "estranhas" são as colunas SEM papel que têm cabeçalho ou conteúdo —
    é onde mora o check do comprador. Devolvê-las é o ponto: uma coluna que o
    sistema não escreveu é, por definição, coisa que ele acrescentou."""
    melhor = (0, {}, [])
    for r in range(1, min(ws.max_row, limite) + 1):
        papeis, vistos = {}, set()
        for c in range(1, ws.max_column + 1):
            papel, moeda = papel_da_coluna(ws.cell(r, c).value)
            if papel is None:
                continue
            chave = 'recusados_rmb' if (papel == 'recusados' and moeda) else papel
            if chave in vistos:      # cabeçalho repetido: fica o 1º
                continue
            vistos.add(chave)
            papeis[chave] = c
        if len(papeis) > len(melhor[1]):
            estranhas = [c for c in range(1, ws.max_column + 1)
                         if c not in papeis.values()]
            melhor = (r, papeis, estranhas)
    if len(melhor[1]) < _MIN_PAPEIS:
        return 0, {}, []
    return melhor


def _vazia(ws, r, cols):
    return all(ws.cell(r, c).value in (None, '') for c in cols)


def le_resumo(ws):
    """As linhas de CATEGORIA da aba Resumo, na ordem em que ele as vê.

    Devolve ``{'linhas': [...], 'faixas': [...], 'total': {...}|None,
    'cabecalho': int, 'papeis': {...}}``.

    Três formas de linha convivem na mesma aba e não podem se misturar:

      · CATEGORIA — a linha de preço. É a única que este arquivo compara.
      · FAIXA DA MARCA — o subtotal que abre cada marca (`_faixa_da_marca`).
        Reconhecida por não ter tipo NEM caixa. Somar categoria e faixa juntas
        dobraria o lote inteiro, e o erro sairia bonito: dá exatamente 2×.
      · RODAPÉ — 'Total · 9 marcas'.

    ⚠ A MARCA vem da coluna quando ela existe (export até 09/2026) e, quando
      não, é HERDADA da faixa acima (export atual, que tirou a coluna porque a
      faixa já diz a marca). Sem a herança, toda linha do formato novo sairia
      com marca vazia e NENHUMA casaria com o banco — 100% de "linha some",
      que é o relatório mais alarmante e mais falso possível.
    """
    cab, papeis, estranhas = mapa_de_colunas(ws)
    if not papeis:
        return {'linhas': [], 'faixas': [], 'total': None,
                'cabecalho': 0, 'papeis': {}, 'estranhas': []}

    def cel(r, papel):
        c = papeis.get(papel)
        return ws.cell(r, c).value if c else None

    usadas = list(papeis.values())
    linhas, faixas, total = [], [], None
    marca_corrente = ''
    for r in range(cab + 1, ws.max_row + 1):
        if _vazia(ws, r, usadas + estranhas):
            continue
        marca_cel = cel(r, 'marca')
        tipo, caixa = cel(r, 'tipo'), cel(r, 'caixa')
        bruto = {p: cel(r, p) for p in papeis}
        comum = {
            'linha': r,
            'marca': str(marca_cel).strip() if marca_cel else marca_corrente,
            'tipo': str(tipo).strip() if tipo else '',
            'capacidade': (str(cel(r, 'capacidade')).strip()
                           if cel(r, 'capacidade') else ''),
            'caixa': str(caixa).strip() if caixa else '',
            'enviados': numero(cel(r, 'enviados')),
            'unit': numero(cel(r, 'unit')),
            'recusados': numero(cel(r, 'recusados')),
            'aprovados': numero(cel(r, 'aprovados')),
            'esperado': numero(cel(r, 'esperado')),
            'resultado': numero(cel(r, 'resultado')),
            'bruto': bruto,
        }
        # RODAPÉ: o texto do total mora na 1ª coluna e não é marca nenhuma.
        primeira = normaliza(ws.cell(r, 1).value)
        if primeira.startswith('total') or primeira.startswith('合计'):
            total = comum
            continue
        if _e_faixa(comum, papeis):
            # ⚠ A faixa lê a célula CRUA, nunca o `comum['marca']`: aquele já
            #   vem com a herança da faixa ANTERIOR aplicada, e usá-lo aqui
            #   faria toda faixa repetir a primeira marca do arquivo — a
            #   segunda marca em diante simplesmente não existiria, e suas
            #   linhas sairiam todas como 'só na planilha'. Foi o que o teste
            #   de ida-e-volta pegou: 'Samsung   2 linhas' virava 'Micron'.
            comum['marca'] = _marca_da_faixa(marca_cel or tipo) or marca_corrente
            marca_corrente = comum['marca']
            comum['marca'] = marca_corrente
            faixas.append(comum)
            continue
        marca_corrente = comum['marca'] or marca_corrente
        comum['marca'] = marca_corrente
        comum.update(marcas_do_comprador(ws, r, estranhas))
        linhas.append(comum)
    return {'linhas': linhas, 'faixas': faixas, 'total': total,
            'cabecalho': cab, 'papeis': papeis, 'estranhas': estranhas}


#: A faixa escreve a marca e, coladas, quantas linhas ela soma
#: ('Micron   3 linhas'), separadas por 3 espaços. Nenhuma marca do catálogo
#: tem espaço duplo no nome — 'SK Hynix' e 'Toshiba-Kioxia' são o pior caso.
_DEPOIS_DA_MARCA = re.compile(r'\s{2,}')


def _marca_da_faixa(txt):
    return _DEPOIS_DA_MARCA.split(str(txt or '').strip())[0].strip()


def _e_faixa(linha, papeis):
    """A linha é a FAIXA da marca (subtotal), não uma categoria?

    O sinal é a CAIXA WTC vazia: toda categoria tem código de caixa — '—'
    quando o PN não tem chave de preço, mas nunca vazio (`result_rows` já
    resolve o travessão). A faixa não tem: ela MESCLA TIPO..WTC para escrever
    a marca, e as células mescladas voltam vazias.

    Sem a coluna de caixa (export mais antigo que ela), o sinal cai para
    capacidade e ¥ unitário — que a faixa também não escreve. É queda, não
    equivalência: por isso a coluna vem primeiro quando existe."""
    if 'caixa' in papeis:
        return not linha['caixa']
    return not linha['capacidade'] and linha['unit'] is None


def marcas_do_comprador(ws, r, estranhas):
    """``{'check': bool, 'check_texto': str, 'check_ilegivel': bool}``.

    O check é o que ele usou para dizer "mexi nesta". Não é campo do sistema:
    é uma coluna que ele criou, então a regra é grosseira de propósito —
    qualquer texto visível conta.

    ⚠ `check_ilegivel` existe porque no arquivo real há uma célula com UM
      ESPAÇO (Samsung LPDDR3 4GB, linha 77). Espaço não é marca e não pode
      virar uma; mas também não é célula vazia — alguém digitou ali. Tratar as
      duas como a mesma coisa esconderia a única linha em que a intenção dele
      é ambígua, que é exatamente a que vale perguntar."""
    textos, tocou = [], False
    for c in estranhas:
        v = ws.cell(r, c).value
        if v is None:
            continue
        tocou = True
        s = str(v).strip()
        if s:
            textos.append(s)
    return {'check': bool(textos), 'check_texto': ' '.join(textos),
            'check_ilegivel': tocou and not textos}


def le_chips(ws):
    """A aba de detalhe, PN a PN. Segunda testemunha do preço ORIGINAL.

    Ela vale ouro na auditoria por um acidente feliz: o comprador edita o
    RESUMO (é onde estão as categorias) e quase nunca desce até os 434 PNs.
    Então o ¥ da aba Chips costuma ser o que SAIU do sistema — e confirma, sem
    o banco, o que ele mudou. É testemunha, não juiz: se ele editar as duas
    abas, quem decide continua sendo a Ordem de Venda."""
    cab, papeis, _ = mapa_de_colunas(ws)
    if not papeis or 'pn' not in papeis:
        return {'linhas': [], 'total': None, 'cabecalho': cab}

    def cel(r, papel):
        c = papeis.get(papel)
        return ws.cell(r, c).value if c else None

    usadas = list(papeis.values())
    linhas, total = [], None
    for r in range(cab + 1, ws.max_row + 1):
        if _vazia(ws, r, usadas):
            continue
        pn = cel(r, 'pn')
        primeira = normaliza(pn)
        item = {
            'linha': r,
            'pn': str(pn).strip() if pn else '',
            'marca': str(cel(r, 'marca')).strip() if cel(r, 'marca') else '',
            'tipo': str(cel(r, 'tipo')).strip() if cel(r, 'tipo') else '',
            'spec': str(cel(r, 'spec')).strip() if cel(r, 'spec') else '',
            'caixa': str(cel(r, 'caixa')).strip() if cel(r, 'caixa') else '',
            'qtd': numero(cel(r, 'qtd')),
            'unit': numero(cel(r, 'unit')),
            'total': numero(cel(r, 'total')),
        }
        if primeira.startswith('total') or primeira.startswith('合计'):
            total = item
            continue
        linhas.append(item)
    return {'linhas': linhas, 'total': total, 'cabecalho': cab,
            'papeis': papeis}


def abas(caminho):
    """``(resumo, chips)`` — as duas abas do arquivo devolvido.

    Escolhe por CONTEÚDO, não por nome nem por posição: a aba se chama
    'Resumo'/'Resumen'/'Summary'/'摘要' conforme o idioma em que ele exportou,
    e quem passou o arquivo por outra ferramenta pode ter reordenado. A aba
    com coluna de PN é a de chips; a outra é o resumo."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=False)
    resumo = chips = None
    for ws in wb.worksheets:
        _, papeis, _ = mapa_de_colunas(ws)
        if not papeis:
            continue
        if 'pn' in papeis and chips is None:
            chips = le_chips(ws)
        elif resumo is None:
            resumo = le_resumo(ws)
    return resumo, chips


#: Nome humano de cada diferença. O relatório do terminal imprime a chave
#: crua; aqui, onde o leitor é o COMPRADOR, ela vira frase — e a frase é
#: neutra de propósito: "¥ unitário alterado" descreve, "preço rebaixado"
#: acusa, e o documento tem de sobreviver a estar errado sobre a intenção.
FRASE = {
    'preco': '¥ unitário alterado',
    'preco_apagado': '¥ unitário apagado',
    'enviados': 'quantidade enviada alterada',
    'recusa': 'recusa declarada',
    'conta_aprovados': 'aprovados ≠ enviados − recusa',
    'conta_resultado': '¥ resultado ≠ aprovados × ¥',
}
