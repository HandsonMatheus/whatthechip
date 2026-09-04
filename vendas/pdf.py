"""PDF da Ordem de Venda (F11.2c — dono: "simples, sem timbre").

Padrão do pricing/pdf.py (reportlab platypus, i18n eager sob o idioma da
sessão, dinheiro com ponto). Reusa os helpers CJK de lá (fonte embutida por
RUN — pegadinhas 1-3 do F9 já resolvidas). O nome do comprador NÃO aparece
(sigilo de plataforma). Sem banco aqui: recebe as linhas prontas da view.
"""

from datetime import date
from decimal import Decimal
from io import BytesIO
from itertools import groupby
from pathlib import Path

from django.utils.translation import gettext as _

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Helpers CJK compartilhados (F9): fonte TTF embutida + runs por trecho.
from pricing.pdf import _cjk_font, _draw_mixed, _rich

#: A MONO DO DESIGN SYSTEM, embutida (dono, 2026-09-04: "se tiver uma fonte
#: monoespacada que seja mais narrow por favor pra ficar mais proximo da
#: interface"). É a mesma `--font-mono:'IBM Plex Mono'` do `typography.css`,
#: no peso SemiBold que o `.dtab th` usa (600).
#:
#: ⚠ ELA NÃO É MAIS ESTREITA QUE A COURIER. Toda monoespaçada de texto avança
#:   600/1000 por caractere — Plex, Courier, Roboto Mono, JetBrains Mono, as
#:   mesmas 600. O que faz a tela parecer mais apertada é o DESENHO (altura de
#:   x maior, hastes mais grossas, menos ar dentro da letra), não a métrica.
#:   Quem resolveu a quebra de linha foi a repartição das colunas, aqui
#:   embaixo — a fonte resolveu a semelhança com a interface.
#:
#: ⚠ Só o cabeçalho da tabela a usa. O resto do papel segue em Helvetica: a
#:   Manrope do sistema não está embutida, e trocar a base mexeria no
#:   `_rich`/`_draw_mixed`. Isto aqui é seguro porque o `_rich` só marca os
#:   RUNS CJK — a fonte-base vem do estilo do parágrafo e não é assumida.
_MONO_TTF = Path(__file__).resolve().parent / 'assets' / 'IBMPlexMono-SemiBold.ttf'


def _mono_font():
    """`WTC-Mono` se a TTF veio no deploy; `Courier-Bold` se não veio.

    O fallback não é decoração: se o arquivo faltar em produção, o
    `registerFont` estoura e o comprador fica sem o PDF do resultado por causa
    de uma fonte. Um cabeçalho na mono errada é um defeito visual; um PDF que
    não abre é uma venda parada.
    """
    if 'WTC-Mono' in pdfmetrics.getRegisteredFontNames():
        return 'WTC-Mono'
    try:
        pdfmetrics.registerFont(TTFont('WTC-Mono', str(_MONO_TTF)))
        return 'WTC-Mono'
    except Exception:
        return 'Courier-Bold'

_INK = colors.HexColor('#161616')
_GREY = colors.HexColor('#8d8d8d')
_LINE = colors.HexColor('#d0d0d0')
_ZEBRA = colors.HexColor('#f4f4f4')
_BLUE = colors.HexColor('#0f62fe')
# Fundos de leve para as duas caixas que o cliente procura primeiro no
# resultado (dono, 2026-08-19): o FINAL em azul, a DIFERENÇA em amarelo.
# Tons 10 do Carbon — claros o bastante para o texto preto continuar legível
# e para não virar borrão quando o PDF sai impresso em preto e branco.
_SKY  = colors.HexColor('#edf5ff')      # azul 10  → resultado final
_SAND = colors.HexColor('#fcf4d6')      # amarelo 10 → diferença

# ── TOKENS DO DESIGN SYSTEM (static/wtc/tokens/colors.css) ────────────────
# ⚠ Os cinco `_` acima são os NEUTROS do Carbon e FICARAM de propósito: o
# packing list e o documento do gerente ainda os usam, e restilizá-los de
# carona numa mudança que o dono pediu para o PDF do RESULTADO seria efeito
# colateral, não escopo — aqueles dois papéis vão para transportadora e
# alfândega. Quando forem alinhados, é para APAGAR os de cima, não para
# manter dois cinzas no mesmo arquivo para sempre.
#
# Os `_T_` abaixo são os hex LITERAIS do `colors.css`. A diferença entre um
# conjunto e outro é de poucos graus de temperatura e some numa olhada
# isolada; lado a lado com a tela, o papel parecia de outro produto.
_T_INK     = colors.HexColor('#161616')   # --ink-100  · texto
_T_INK90   = colors.HexColor('#21272a')   # --ink-90   · cabeçalho de tabela
_T_INK70   = colors.HexColor('#4d5358')   # --ink-70   · rótulo do esperado
_T_MUTED   = colors.HexColor('#697077')   # --ink-60   · rótulo
_T_FAINT   = colors.HexColor('#878d96')   # --ink-50   · apagado
_T_LINE    = colors.HexColor('#dde1e6')   # --ink-20   · fio entre linhas
_T_LINE2   = colors.HexColor('#c1c7cd')   # --ink-30   · fio forte
_T_SURF2   = colors.HexColor('#f2f4f8')   # --ink-10   · faixa de marca
_T_SURF3   = colors.HexColor('#f7f8fb')   # --ink-05   · painel de informação
_T_BLUE    = colors.HexColor('#0f62fe')   # --blue-60
_T_BLUE70  = colors.HexColor('#0043ce')   # --blue-70  · o número final
_T_SKY     = colors.HexColor('#edf5ff')   # --blue-10
_T_MINT    = colors.HexColor('#e6f7ec')   # --green-10 · coluna aprovados
_T_GREEN40 = colors.HexColor('#42be65')   # --green-40 · rótulo aprovados
_T_ROSE    = colors.HexColor('#fff1f1')   # --red-10   · coluna recusados
_T_RED50   = colors.HexColor('#fa4d56')   # --red-50   · rótulo recusados
_T_GREEN50 = colors.HexColor('#24a148')   # --green-50
_T_GREEN   = colors.HexColor('#0e6027')   # --green-70
_T_SAND    = colors.HexColor('#fdf3d6')   # --amber-10 (o antigo era #fcf4d6)
_T_AMBER40 = colors.HexColor('#f1c21b')   # --amber-40
_T_AMBER   = colors.HexColor('#8a6a00')   # --amber-70
_T_RED     = colors.HexColor('#a2191f')   # --red-70   · recusa


def _mistura(base, tinta, peso=0.12):
    """O `color-mix(in srgb, base X%, tinta)` do CSS, em reportlab.

    O design system NÃO tem um passo 20 de vermelho nem de verde — a rampa vai
    de 10 direto para 40. Quando a tela precisa da MESMA tinta um tom abaixo,
    ela não inventa um hex: mistura os dois passos que existem. É literalmente
    o que o `components.css` faz no realce das duas colunas do julgamento::

        .dtab tbody tr:hover td.hr{background:color-mix(in srgb,var(--red-10) 88%,var(--red-50))}
        .dtab tbody tr:hover td.hg{background:color-mix(in srgb,var(--green-10) 88%,var(--green-50))}

    Reproduzir a receita em vez de cravar um `#feddde` no arquivo é o que
    mantém papel e tela na mesma paleta: no dia em que `--red-10` mudar, os
    dois se movem juntos. Um token novo em `colors.css` que só o PDF usasse
    seria pior — passo de paleta que ninguém mais usa é mentira em design
    system.

    `in srgb` mistura os canais já codificados em gama, sem converter espaço,
    então é média ponderada simples e direta.
    """
    resto = 1.0 - peso
    return colors.Color(base.red * resto + tinta.red * peso,
                        base.green * resto + tinta.green * peso,
                        base.blue * resto + tinta.blue * peso)


# A linha de TOTAL — a faixa de cada marca e o total geral — leva as mesmas
# duas colunas um tom abaixo, "pra se entender que tá mostrando o total"
# (dono, 2026-09-04). O peso é o do realce da tela.
_T_ROSE_TOT = _mistura(_T_ROSE, _T_RED50)
_T_MINT_TOT = _mistura(_T_MINT, _T_GREEN50)


#: Máscara de valor (dono, 2026-08-14). Glifo, não string traduzível — igual
#: nos 4 idiomas. ⚠ Aqui é '*' e não o '•••' da TELA de propósito: a Helvetica
#: do reportlab não tem o bullet no vetor WinAnsi e ele sai como 0x7F (célula
#: em branco / quadradinho no leitor) — conferido no PDF gerado.
_MASK = '***'


def render_so_pdf(so, rows, total_rmb, total_usd, fx_rate, masked=False) -> bytes:
    """``rows`` = [{label, qty, unit_rmb, total_rmb, total_usd}] (strings já
    formatadas; sem-preço vem com unit_rmb=None e reason no label).

    ``masked=True`` (dinheiro e taxa como ``***``) continua funcionando, mas
    **a view não usa mais**: desde 2026-08-18 quem não vê preço recebe o
    ``render_so_manager_pdf`` (documento próprio, sem coluna de dinheiro
    nenhuma) em vez deste com as células tampadas."""
    t_title = _('Ordem de venda')
    if so.status == 'draft':
        t_status = _('cotação — valores vivos')
    elif so.status == 'confirmed':
        t_status = _('confirmada — valores congelados')
    else:
        t_status = _('cancelada')
    t_issued = _('Emitido em')
    t_by = _('Gerado por WhatTheChip')
    t_rate = _('taxa')
    heads = [_('Categoria'), _('Qtd.'), _('¥ unit.'), _('Total ¥'),
             _('Total US$')]
    t_total = _('Total')

    font, bold = 'Helvetica', 'Helvetica-Bold'
    cjk = _cjk_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title=f'{so.code} — {t_title}', author='WhatTheChip')
    avail = A4[0] - 28 * mm

    st_h1 = ParagraphStyle('h1', fontName=bold, fontSize=16, leading=19,
                           textColor=_INK)
    st_sub = ParagraphStyle('sub', fontName=font, fontSize=8.5, leading=11.5,
                            textColor=_GREY)

    issued = date.today().strftime('%d/%m/%Y')
    _taxa = _MASK if masked else f'1 CNY = {fx_rate} USD'
    sub = (f'{t_title} · {t_status} · {so.lot.code} · '
           f'{t_rate} {_taxa} · {t_issued} {issued}')

    story = [
        Paragraph(_rich(f'{so.code}', cjk), st_h1),
        Paragraph(_rich(sub, cjk), st_sub),
        Spacer(0, 6),
    ]

    widths = [0.44 * avail, 0.10 * avail, 0.14 * avail, 0.16 * avail,
              0.16 * avail]
    st_th = ParagraphStyle('th', fontName=bold, fontSize=7.5, leading=9,
                           textColor=_INK)
    data = [[Paragraph(_rich(h, cjk), st_th) for h in heads]]
    styles = []
    for i, r in enumerate(rows, start=1):
        if masked:
            data.append([r['label'], r['qty'], _MASK, _MASK, _MASK])
            styles.append(('TEXTCOLOR', (2, i), (4, i), _GREY))
        elif r['unit_rmb'] is not None:
            data.append([r['label'], r['qty'], f"¥ {r['unit_rmb']}",
                         f"¥ {r['total_rmb']}", f"US$ {r['total_usd']}"])
        else:
            data.append([r['label'], r['qty'], '—', '—', '—'])
            styles.append(('TEXTCOLOR', (2, i), (4, i), _GREY))
        if i % 2 == 0:
            styles.append(('BACKGROUND', (0, i), (-1, i), _ZEBRA))
    # Linha de total:
    if masked:
        data.append([t_total, '', '', _MASK, _MASK])
    else:
        data.append([t_total, '', '', f'¥ {total_rmb}', f'US$ {total_usd}'])
    last = len(data) - 1
    styles += [
        ('FONT', (0, last), (-1, last), bold, 8.5, 10),
        ('LINEABOVE', (0, last), (-1, last), 0.8, _INK),
    ]

    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), font, 8, 9.6),
        ('TEXTCOLOR', (0, 0), (-1, -1), _INK),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, _LINE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, _INK),
        ('TOPPADDING', (0, 0), (-1, -1), 2.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ] + styles))
    story.append(t)

    footer_txt = f'{so.code} · {t_by} · {issued}'

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_GREY)
        _draw_mixed(canvas, 14 * mm, 9 * mm, footer_txt, 6.5, font, cjk)
        canvas.setFont(font, 6.5)
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm,
                               str(canvas.getPageNumber()))
        canvas.setStrokeColor(_BLUE)
        canvas.setLineWidth(0.8)
        canvas.line(14 * mm, 11.2 * mm, A4[0] - 14 * mm, 11.2 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()




# ═══ Documento do LOTE / EMBARQUE (dono, 2026-08-18) ════════════════════════
#
# UM documento só, em duas versões: sem preço (gerente/operador) e com preço
# (admin da empresa) — "a única diferença é que tem preços" (dono). Ele é ao
# mesmo tempo a conferência do lote e o papel que viaja com o pacote na DHL.
#
# ⚠ SEMPRE EM INGLÊS + 繁體中文 entre parênteses, independente do idioma da
# sessão. Motivo (dono): o documento é lido pela transportadora e pelo
# destinatário em Macau — idioma de documento de embarque é do TRANSPORTE, não
# de quem clicou. Por isso os rótulos NÃO passam por gettext: são CANÔNICOS,
# como o código de caixa (LETRA-##) e o `SO/NUM/MM/YY`. Um `{% trans %}` aqui
# faria o papel mudar de língua conforme quem apertou o botão — o oposto do
# que um documento de embarque precisa.
#
# Chinês é TRADICIONAL (繁體) de propósito: Macau/Hong Kong/Taiwan. Não é o
# catálogo zh-hans da interface (simplificado) — não reuse um pelo outro.

#: Rótulo → (inglês, 繁體中文). Fonte ÚNICA dos textos do documento.
_L = {
    # ⚠ 2026-08-20: era 'Sales order' / 'Lot check'. Virou REFERÊNCIA e PACKING
    # LIST a pedido do dono — *"não fale nada de aduana de Macao, nem que isso
    # vai ser vendido, nem que a aduana vai conferir, ou que tem despacho"*.
    # Não é uma exportação: é remessa simples. Papel que se anuncia como venda
    # internacional pede tratamento de venda internacional.
    'so':         ('Reference',            '參考編號', 'Referencia'),
    'lot':        ('Lot',                  '批次'),
    'doc':        ('Packing list',         '裝箱單', 'Lista de empaque'),
    'draft':      ('quotation',            '報價'),
    'confirmed':  ('confirmed',            '已確認'),
    'cancelled':  ('cancelled',            '已取消'),
    'ship_from':  ('SHIP FROM',            '寄件人'),
    'ship_to':    ('SHIP TO',              '收貨人'),
    'issued':     ('Issued on',            '簽發日期'),
    'closed':     ('Lot closed on',        '批次關閉日期'),
    'closed_by':  ('Closed by',            '關閉人'),
    'fx':         ('Exchange rate',        '匯率'),
    'wtc':        ('WTC categories',       'WTC 類別'),
    'spec':       ('Summary by chip type', '晶片類型彙總'),
    'category':   ('Category',             '類別'),
    'qty':        ('Qty.',                 '數量'),
    'type':       ('Type',                 '類型'),
    'capacity':   ('Capacity',             '容量'),
    'nocat':      ('No category',          '無類別'),
    'total':      ('Total',                '總計'),
    'unit_rmb':   ('Unit ¥',               '單價'),
    #: ⚠ SEM a moeda no título: a célula abaixo abre em US$ e traz o ¥
    #: embaixo (2026-09-04). Um "Unit ¥" sobre um valor em dólar anuncia a
    #: moeda errada na primeira leitura — o mesmo defeito que a tela do
    #: comprador teve na mesma entrega. O `unit_rmb`/`total_rmb` ficam para os
    #: OUTROS dois documentos, que seguem só em ¥.
    'unit':       ('Unit',                 '單價'),
    'total_rmb':  ('Total ¥',              '總計 ¥'),
    'total_usd':  ('Total US$',            '總計 US$'),
    'generated':  ('Generated by WhatTheChip', '由 WhatTheChip 產生'),
    # ── Declaração aduaneira do embarque (dono, 2026-08-18) ────────────────
    # ⚠ Estas entradas têm TRÊS idiomas (EN · 中文 · ES) desde 2026-08-20: o
    # documento de despacho passou a ser trilíngue, com o inglês como
    # principal. O `_t()` (bilíngue) continua lendo só os dois primeiros, então
    # o PDF do RESULTADO não muda; quem usa os três é o `_t3()`.
    'contents':   ('Description of contents', '內容物描述',
                   'Descripción del contenido'),
    'declared':   ('Declared value',       '申報價值', 'Valor declarado'),
    'carrier':    ('Carrier',              '承運人', 'Transportista'),
    'tracking':   ('Tracking number',      '追蹤號碼', 'Número de seguimiento'),
    'shipped_on': ('Shipped on',           '發貨日期', 'Enviado el'),
    # ── ANEXO (dono, 2026-08-20, 4ª rodada: *"cadê o anexo legal? você removeu
    # tudo em vez de adaptar"*) ─────────────────────────────────────────────
    # ⚠ Os títulos são a parte MAIS sensível do anexo: são o que se lê de
    # relance. Nenhum deles pode conter aduana, Macau, venda, desembaraço ou
    # exportação — foi a instrução literal. Por isso "Annex — declaration on
    # the goods" e não "Regulatory annex", e "End use" e não "Export control".
    'annex':      ('Annex — declaration on the goods',
                   '附件 — 貨物聲明',
                   'Anexo — declaración sobre la mercancía'),
    'a_nature':   ('1. Nature of the goods',
                   '1. 貨物性質',
                   '1. Naturaleza de la mercancía'),
    'a_use':      ('2. End use',
                   '2. 最終用途',
                   '2. Uso final'),
    # ── Documento do RESULTADO (dono, 2026-08-18) ──────────────────────────
    'result':     ('Purchase result',      '採購結果'),
    'detail':     ('Result detail',        '結果明細'),
    #: ⚠ NÃO reaproveite o `so` aqui, e não troque o `so` por isto.
    #:
    #: O `so` diz "Reference" desde 2026-08-20 por decisão explícita do dono:
    #: *"não fale nada de aduana de Macao, nem que isso vai ser vendido, nem
    #: que a aduana vai conferir, ou que tem despacho"*. Quem carrega aquele
    #: rótulo é o PACKING LIST, que viaja com a carga — papel de remessa que
    #: se anuncia como venda internacional pede tratamento de venda
    #: internacional.
    #:
    #: Este documento é outro: sai do comprador para o CLIENTE, já se chama
    #: "Purchase result" no título e não viaja com caixa nenhuma. Aqui "Sales
    #: Order" é o nome certo (dono, 2026-09-04) — e por isso é chave separada,
    #: para o pedido de um documento nunca reetiquetar o outro.
    'so_result':  ('Sales Order',           '銷售訂單'),
    #: MESMO MOTIVO, outro rótulo. O `ship_from` em CAIXA ALTA é a convenção
    #: do documento de EMBARQUE — packing list e transportadora leem "SHIP
    #: FROM"/"SHIP TO" em caixa alta no mundo inteiro, e o `_caixa_endereco`
    #: depende disso. O papel do resultado não viaja com caixa: ali o rótulo
    #: é um campo como "Lot closed on" e tem de ter a mesma caixa que os
    #: vizinhos (dono, 2026-09-04). Chave separada para um não mexer no
    #: outro — é a mesma armadilha do `so`/`so_result`.
    'ship_from_r': ('Ship from',           '寄件人'),
    #: A PROCEDÊNCIA do material (dono, 2026-09-04). "Lot origin" e não só
    #: "Origin": num papel que atravessa alfândega, "origin" sozinho lê como
    #: PAÍS de origem, que é outra coisa e das caras de errar.
    'lot_origin': ('Lot origin',          '批次來源'),
    'expected':   ('Expected',             '預期'),
    #: "Final" sozinho não diz final DE QUÊ — ao lado de "Expected" e
    #: "Difference" o leitor tem de deduzir. 最終 é o mesmo problema em
    #: chinês: é o adjetivo, não a coisa. 最終結果 é o substantivo completo
    #: (dono, 2026-09-04). Só o PDF do resultado usa esta chave.
    'final':      ('Final result',         '最終結果'),
    'difference': ('Difference',           '差額'),
    'received':   ('Box received on',      '收貨日期'),
    'settled':    ('Result closed on',     '結果確認日期'),
    'sent':       ('Sent',                 '寄出'),
    'rejected':   ('Rejected',             '拒收'),
    'accepted':   ('Accepted',             '接收'),
    'brand':      ('Brand',                '品牌'),
    'notes':      ('Notes',                '備註'),
    # A AUTORIA das observações no papel (spec v2 do comprador §7.1): quem
    # escreveu foi o comprador, mas quem lê é o cliente — e de quem o
    # WhatTheChip compra é sigilo. O documento diz que a CONFERÊNCIA falou,
    # não quem conferiu.
    'checked_by': ('Conference',           '驗貨'),
}


#: ANEXO — DECLARAÇÃO SOBRE A MERCADORIA (dono, 2026-08-20, 4ª rodada).
#:
#: ⚠ Este anexo já foi TRÊS coisas no mesmo dia. A história importa porque cada
#: versão foi derrubada por um motivo diferente, e é fácil "melhorar" de volta:
#:
#:   v1  não existia — e o papel dizia `PCB CHIPS FOR DISPOSAL`, que sozinho
#:       declarava resíduo e convocava o PIC de Basileia. Era a causa do
#:       bloqueio na transportadora.
#:   v2  três seções longas: natureza + licenciamento de importação em Macau +
#:       controle de exportação americano, com lei citada por extenso. Correto,
#:       e **exagerado**: o sócio do dono apontou que citar despacho aduaneiro
#:       num papel de remessa simples chama atenção justamente para o assunto
#:       que não interessa levantar.
#:   v3  removido inteiro. Erro meu de leitura — o dono pediu **adaptar**, não
#:       apagar: *"cadê o anexo legal? você removeu tudo em vez de adaptar"*.
#:
#: Esta é a v4, e o critério que a define é simples: **o anexo declara o que a
#: MERCADORIA é, e nada sobre o trâmite.** Some tudo que a instrução literal do
#: dono proibiu — *"não fale nada de aduana de Macao, nem que isso vai ser
#: vendido, nem que a aduana vai conferir, ou que tem despacho"*:
#:
#:   · a seção inteira de licenciamento de importação em Macau — SAIU;
#:   · "sold to the consignee under a commercial invoice" — SAIU (venda);
#:   · "no prior informed consent NOTIFICATION is applicable to this shipment"
#:     — vira a conclusão sem o vocabulário de procedimento entre Estados;
#:   · "United States Commerce Control List", "export control regimes",
#:     "controls applicable to the Macao SAR" — SAIU; sobra o ECCN, que é a
#:     referência técnica do parâmetro, sem nomear regime;
#:   · "end-of-life devices" — vira "consumer electronic equipment": não há
#:     motivo para o papel usar a palavra que descreve fim de vida útil.
#:
#: O que SOBRA é o que sustenta a carga em qualquer destino, sem se referir a
#: nenhum: são componentes funcionais testados para reuso (não resíduo, logo
#: fora de Y49/A1181 de Basileia) e o uso final é civil e comercial.
#:
#: ⚠ A versão COMPLETA, com Macau e controle de exportação, está guardada em
#: `DESPACHO_MACAU_CONFORMIDADE.md §6`. Ela é para RESPONDER quando
#: perguntarem — não para viajar impressa.
_ANEXO = (
    ('a_nature', (
        'The goods listed in this document are electronic integrated circuits '
        'recovered from consumer electronic equipment. Each unit has been '
        'individually identified by part number, functionally tested, graded '
        'and classified by category. They are functional electronic components '
        'intended for direct reuse. They are NOT waste and NOT scrap, and are '
        'not consigned for disposal, recycling or recovery operations. '
        'Accordingly they do not fall within entry Y49 (used and end-of-life '
        'electrical and electronic equipment) or entry A1181 of the Basel '
        'Convention on the Control of Transboundary Movements of Hazardous '
        'Wastes and their Disposal, as amended with effect from 1 January '
        '2025, and the consent procedure established by that Convention does '
        'not apply to these goods. The category and quantity table in this '
        'document evidences their tested and graded condition.',
        '本文件所列貨物為自消費電子設備中回收之電子集成電路。每件均已按型號個別'
        '識別、功能測試、分級並歸類，屬可直接再使用之功能性電子元件。該等貨物'
        '並非廢棄物、並非廢料，亦非付運作處置、回收或再生作業之用。因此，不屬於'
        '《控制危險廢物越境轉移及其處置巴塞爾公約》（經修訂，自二零二五年一月'
        '一日生效）之 Y49 條目（使用過及報廢電氣電子設備）或 A1181 條目，該公約'
        '所設之同意程序並不適用於本批貨物。本文件之類別及數量表足證其已測試及'
        '分級之狀態。',
        'Las mercancías indicadas en este documento son circuitos integrados '
        'electrónicos recuperados de equipos electrónicos de consumo. Cada '
        'unidad ha sido identificada individualmente por número de parte, '
        'probada funcionalmente, clasificada por grado y por categoría. Son '
        'componentes electrónicos funcionales destinados a su reutilización '
        'directa. NO son residuo y NO son chatarra, y no se consignan para '
        'eliminación, reciclaje ni operaciones de recuperación. En '
        'consecuencia, no están comprendidas en la entrada Y49 (equipos '
        'eléctricos y electrónicos usados y al final de su vida útil) ni en la '
        'entrada A1181 del Convenio de Basilea sobre el Control de los '
        'Movimientos Transfronterizos de los Desechos Peligrosos y su '
        'Eliminación, en su versión modificada con efecto desde el 1 de enero '
        'de 2025, y el procedimiento de consentimiento establecido por dicho '
        'Convenio no les resulta aplicable. El cuadro de categorías y '
        'cantidades de este documento acredita su condición probada y '
        'clasificada.')),
    ('a_use', (
        'The goods are commodity memory integrated circuits (such as eMMC, '
        'eMCP, uMCP, UFS, DDR and LPDDR devices). They are not advanced '
        'computing items and do not meet the parameters of ECCN 3A090 or '
        '4A090. They are intended exclusively for legitimate civil and '
        'commercial use. The shipper declares that the goods are not intended, '
        'in whole or in part, for any military end use, for any nuclear, '
        'chemical or biological weapons application, nor for any end user '
        'subject to applicable sanctions.',
        '本批貨物為通用記憶體集成電路（如 eMMC、eMCP、uMCP、UFS、DDR 及 LPDDR '
        '器件），並非先進運算物項，不符合 ECCN 3A090 或 4A090 之參數，僅供合法'
        '民用及商業用途。發貨人聲明：貨物之全部或部分並非用於任何軍事最終用途、'
        '任何核子、化學或生物武器用途，亦非供任何受適用制裁措施規限之最終用戶。',
        'Las mercancías son circuitos integrados de memoria de uso común (como '
        'dispositivos eMMC, eMCP, uMCP, UFS, DDR y LPDDR). No son artículos de '
        'computación avanzada y no cumplen los parámetros del ECCN 3A090 ni '
        '4A090. Se destinan exclusivamente a un uso civil y comercial legítimo. '
        'El expedidor declara que las mercancías no se destinan, en todo ni en '
        'parte, a ningún uso final militar, a ninguna aplicación de armas '
        'nucleares, químicas o biológicas, ni a ningún usuario final sujeto a '
        'sanciones aplicables.')),
)


def _t(chave) -> str:
    """``Issued on (簽發日期)`` — o rótulo bilíngue de ``chave``.

    TODO rótulo do documento passa por aqui: título, legenda e cabeçalho de
    coluna (pedido do dono, 2026-08-18 — "ao lado de cada título, de cada
    campo, entre parênteses a tradução em chinês tradicional"). Não crie
    variante "só inglês" para caber numa coluna: aumente a coluna.
    """
    en, zh = _L[chave][0], _L[chave][1]
    return f'{en} ({zh})'


def _t3(chave) -> str:
    """``Carrier (承運人 · Transportista)`` — o rótulo TRILÍNGUE de ``chave``.

    Inglês principal, chinês tradicional e espanhol entre parênteses (dono,
    2026-08-20: *"tudo em inglês, chinês e espanhol, sendo inglês o
    principal"*). Chinês TRADICIONAL de propósito: é um dos idiomas oficiais
    de Macau, destino do embarque — o simplificado é do comprador, não da
    alfândega que vai ler o papel.

    Só o documento de DESPACHO usa os três. O `_t()` bilíngue segue servindo o
    PDF do resultado, que é lido pelo comprador e pelo cliente.

    ⚠ Chave sem espanhol cai no bilíngue em vez de explodir: rótulo faltando é
    defeito de conteúdo, não motivo para o documento inteiro não sair.
    """
    valores = _L[chave]
    if len(valores) < 3:
        return _t(chave)
    en, zh, es = valores[0], valores[1], valores[2]
    return f'{en} ({zh} · {es})'


#: Logo do WhatTheChip. PNG commitado (reportlab não desenha SVG) — a receita
#: de regeneração está no vendas/assets/README.md.
_WTC_LOGO = Path(__file__).resolve().parent / 'assets' / 'wtc-logo.png'

_LOGO_H = 8.5 * mm          # altura no cabeçalho; largura sai da proporção


def _fmt_dt(value, com_hora=False) -> str:
    """dd/mm/aaaa (+ hh:mm) no fuso do servidor. Vazio vira travessão."""
    if value is None:
        return '—'
    if hasattr(value, 'tzinfo') and value.tzinfo is not None:
        from django.utils import timezone
        value = timezone.localtime(value)
    return value.strftime('%d/%m/%Y %H:%M' if com_hora else '%d/%m/%Y')


#: Os meses em inglês, CRAVADOS. `strftime('%B')` obedece à locale do
#: processo — no Render o servidor pode estar em C, pt_BR ou zh_CN, e o
#: rodapé sairia "4 setembro 2026" ou "4 九月 2026" sem ninguém perceber.
#: Este documento é sempre inglês + 中文, independente do idioma da interface.
_MESES_EN = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
             'August', 'September', 'October', 'November', 'December')


def _fmt_extenso(value) -> str:
    """``4 September 2026 (2026年9月4日)`` — a data escrita, nas duas línguas.

    Por extenso porque `04/09/2026` é ambíguo entre quem lê dd/mm e quem lê
    mm/dd, e este papel atravessa os dois mundos: sai do Paraguai e é lido na
    China. Escrito não tem como ler errado (dono, 2026-09-04).

    A ordem inglesa é ``4 September`` e não ``September 4``: é a que não
    inverte em relação ao resto do documento, que já usa dd/mm nos campos.
    A chinesa é a canônica 年月日, sem zero à esquerda — 2026年9月4日, nunca
    2026年09月04日.
    """
    if value is None:
        return '—'
    if hasattr(value, 'tzinfo') and value.tzinfo is not None:
        from django.utils import timezone
        value = timezone.localtime(value)
    en = f'{value.day} {_MESES_EN[value.month - 1]} {value.year}'
    zh = f'{value.year}年{value.month}月{value.day}日'
    return f'{en} ({zh})'


def _img(fonte, altura=_LOGO_H):
    """``Image`` do reportlab com a largura derivada da proporção, ou None se
    a imagem não existe/não abre.

    ``fonte`` = caminho (logo do WTC) ou bytes (logo da empresa, que mora no
    BANCO — CompanyLogo). **Nunca levanta:** logo é enfeite; um PNG corrompido
    no banco de um cliente não pode derrubar o documento de embarque dele.
    """
    from io import BytesIO
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage
    try:
        origem = BytesIO(fonte) if isinstance(fonte, (bytes, memoryview)) \
            else str(fonte)
        if not isinstance(origem, BytesIO) and not Path(origem).exists():
            return None
        larg, alt = ImageReader(origem).getSize()
        if not alt:
            return None
        if isinstance(origem, BytesIO):
            origem.seek(0)
        return RLImage(origem, width=altura * larg / alt, height=altura,
                       hAlign='LEFT')
    except Exception:                      # PNG quebrado, WebP sem suporte…
        return None


def render_so_manager_pdf(doc: dict) -> bytes:
    """PACKING LIST do lote — o papel que viaja com a caixa.

    ⚠ **Reescrito três vezes em 2026-08-20**, e vale saber por quê, porque o
    caminho é o próprio raciocínio:

    1. Era um relatório de conferência com preço, marca e capacidade.
    2. Virou "documento de despacho", com declaração aduaneira, código HS e
       duas páginas de anexo legal — porque a DHL tinha travado um pacote.
    3. Virou **packing list**, quando o sócio do dono apontou o erro de
       enquadramento: *"não estamos fazendo exportação nem despacho... se você
       colocar isso vai chamar atenção para outro assunto, que é o despacho
       aduaneiro, aí só piora"*. É **remessa simples**, não venda
       internacional com desembaraço.

    O princípio que sobrou, e que vale para qualquer papel deste sistema:
    **documento que cita lei convida quem confere a ler a lei.** O que travava
    o pacote era a palavra `DISPOSAL` na descrição — trocada por um texto
    neutro, o problema morre sem precisar de anexo nenhum.

    O que ele tem, e só isso: identificação, remetente e destinatário,
    conteúdo e valor declarado, procedência do fechamento, transportadora /
    rastreio / data, e a quantidade POR CATEGORIA WTC.

    O que NÃO tem, por decisão explícita: preço (é comércio, viaja na
    fatura), marca e capacidade (idem), código HS, título de declaração
    aduaneira, anexo legal, estado da ordem e linha de assinatura.

    ⚠ Com isso ``doc['with_prices']`` não influencia este render: **admin e
    gerente recebem o MESMO documento**. A barreira de dinheiro é estrutural —
    não há coluna de valor aqui para esconder.

    Rótulos em inglês, com 繁體中文 e español entre parênteses: o papel é lido
    pela transportadora e pelo destinatário, não por quem clicou. Por isso NÃO
    passam por gettext — são canônicos.

    ``doc`` = ``vendas.services.manager_document(so, with_prices=…)`` —
    dicionário pronto, sem banco aqui (mesmo contrato do ``render_so_pdf``).

    ⚠ A tabela traz SÓ o código de caixa WTC — nunca marca nem capacidade,
    para ninguém (dono, 2026-08-20). Ver o aviso em ``vendas/services.py``.
    """
    font, bold, mono = 'Helvetica', 'Helvetica-Bold', 'Courier-Bold'
    # force=True: os ideogramas são CONTEÚDO deste documento, não tradução da
    # interface — sem a TTF embutida o reportlab desenha quadradinhos.
    cjk = _cjk_font(force=True)
    buf = BytesIO()
    doc_tpl = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=16 * mm,
        title=f"{doc['so_code']} · {doc['lot_code']}", author='WhatTheChip')
    avail = A4[0] - 28 * mm

    st_cap   = ParagraphStyle('cap', fontName=bold, fontSize=7, leading=9.5,
                              textColor=_GREY)
    # ⚠ MESMO fontSize nos dois códigos (dono: "nenhum é mais importante que o
    # outro"). Mexeu num, mexe no outro — é requisito, não estética.
    st_code  = ParagraphStyle('code', fontName=mono, fontSize=14, leading=17,
                              textColor=_INK)
    # leftIndent=-6 anula o padding do Frame do reportlab: sem ele o texto
    # corrido nasce 6pt à direita das tabelas (que ficam coladas na margem por
    # serem mais largas que a área útil) e a borda esquerda sai serrilhada.
    st_sub   = ParagraphStyle('sub', fontName=font, fontSize=8, leading=11,
                              textColor=_GREY, leftIndent=-6)
    st_sec   = ParagraphStyle('sec', fontName=bold, fontSize=8.5, leading=11,
                              textColor=_INK, spaceAfter=3, leftIndent=-6)
    st_val   = ParagraphStyle('val', fontName=bold, fontSize=8.5, leading=11,
                              textColor=_INK)
    # ⚠ O TÍTULO do documento (dono, 2026-08-20: *"cadê o nome PACKING LIST no
    # PDF? você só mudou o nome do arquivo"*). Um packing list tem que se
    # anunciar como packing list ANTES de qualquer número: é a primeira coisa
    # que a transportadora procura na folha, e legenda cinza de 8pt embaixo
    # dos códigos não é anúncio, é rodapé.
    st_tit   = ParagraphStyle('tit', fontName=bold, fontSize=15, leading=18,
                              textColor=_INK, leftIndent=-6, spaceAfter=1)
    st_th    = ParagraphStyle('th', fontName=bold, fontSize=7, leading=9,
                              textColor=_INK)
    # ⚠ Célula de tabela com IDEOGRAMA tem que ser Paragraph. String crua é
    # desenhada na fonte BASE da tabela (Helvetica) e o CJK sai como lixo
    # WinAnsi — "無類別" virava "nnn" no papel (achado 2026-08-18 pelo teste
    # de glifos). Texto ASCII pode seguir como string.
    st_td    = ParagraphStyle('td', fontName=font, fontSize=8, leading=9.6,
                              textColor=_INK)
    st_tdb   = ParagraphStyle('tdb', fontName=bold, fontSize=8.5, leading=10,
                              textColor=_INK)
    st_ship  = ParagraphStyle('ship', fontName=font, fontSize=8.5, leading=12,
                              textColor=_INK)
    st_shipn = ParagraphStyle('shipn', fontName=bold, fontSize=10, leading=13.5,
                              textColor=_INK)

    def P(txt, estilo):
        return Paragraph(_rich(str(txt), cjk), estilo)

    def _limpa(tabela, styles=()):
        """Tabela SEM grade — usada nos blocos de cabeçalho (o desenho de
        caixa é só das tabelas de dados)."""
        tabela.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ] + list(styles)))
        return tabela

    story = []

    # ── 1. Logos: WhatTheChip à esquerda, empresa-cliente à direita ─────────
    wtc_logo = _img(_WTC_LOGO)
    cli_logo = _img(doc.get('company_logo')) if doc.get('company_logo') else None
    if cli_logo is not None:
        cli_logo.hAlign = 'RIGHT'
    if wtc_logo or cli_logo:
        story += [_limpa(Table([[wtc_logo or '', cli_logo or '']],
                               colWidths=[0.5 * avail, 0.5 * avail]),
                         [('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]),
                  Spacer(0, 9)]

    # ── 2. TÍTULO: o papel diz o que é, antes de dizer de quem é ───────────
    story += [P(_t3('doc'), st_tit), Spacer(0, 5)]

    # ── 2b. Identificação: REFERÊNCIA e LOTE, mesmo peso ────────────────────
    story += [_limpa(Table(
        [[P(_t('so'), st_cap), P(_t('lot'), st_cap)],
         [P(doc['so_code'], st_code), P(doc['lot_code'], st_code)]],
        colWidths=[0.5 * avail, 0.5 * avail]),
        # ⚠ padding na LINHA inteira: diferente entre as duas legendas
        # desalinha as bases e um código parece "maior" que o outro.
        [('BOTTOMPADDING', (0, 0), (-1, 0), 1),
         ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
         ('LINEBELOW', (0, 1), (-1, 1), 1.2, _BLUE)])]

    # ⚠ 2026-08-20: NÃO existe mais linha de subtítulo. Ela trazia o ESTADO da
    # ordem (cotação/confirmada/cancelada) — informação comercial interna, que
    # o dono pediu para tirar — e depois virou o nome do documento em cinza
    # 8pt, que é o mesmo que não ter nome. O nome subiu para o TÍTULO.

    # ── 3. SHIP FROM × SHIP TO, lado a lado (leitura de transportadora) ─────
    def _caixa_endereco(chave, bloco):
        # ⚠ O RÓTULO sai SEMPRE, com ou sem dado. Metade de caixa em branco,
        # sem sequer dizer 'SHIP TO', se lê como falha de impressão — e num
        # documento de embarque a leitura certa é a outra: **está faltando o
        # destinatário**, vá preencher no cadastro do comprador. O travessão
        # deixa o buraco visível para quem imprime, antes de ser visível para
        # a transportadora.
        corpo = [P(_t(chave), st_cap)]
        if not bloco:
            corpo.append(P('\u2014', st_shipn))
            return corpo
        if bloco.get('name'):
            corpo.append(P(bloco['name'], st_shipn))
        for linha in bloco.get('lines') or []:
            corpo.append(P(linha, st_ship))
        contato = ' · '.join(x for x in (bloco.get('email'), bloco.get('phone'))
                             if x)
        if contato:
            corpo.append(P(contato, st_ship))
        return corpo

    de, para = doc.get('ship_from') or {}, doc.get('ship_to') or {}
    # Uma caixa só, dividida ao meio: o remetente à esquerda e o destinatário à
    # direita — o par que a transportadora procura junto. Sai SEMPRE: este é um
    # documento de embarque, e embarque sem remetente e destinatário no papel
    # não existe. Faltando o dado, o campo aparece vazio e cobra quem cadastra.
    enderecos = Table(
        [[_caixa_endereco('ship_from', de),
          _caixa_endereco('ship_to', para)]],
        colWidths=[0.5 * avail, 0.5 * avail])
    enderecos.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, _INK),
        ('LINEAFTER', (0, 0), (0, 0), 0.4, _LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story += [Spacer(0, 10), enderecos]

    # ── 3b. CONTEÚDO E VALOR — exigência da transportadora ─────────────────
    # Descrição e valor SEMPRE preenchidos: campo em branco é o que faz o
    # pacote parar, ou ser reavaliado por quem não conhece a carga.
    #
    # ⚠ 2026-08-20, pedido do dono: **saiu o código HS e saiu o título
    # "Customs declaration"**. Isto não é uma exportação, é remessa simples —
    # e um papel que se anuncia como declaração aduaneira pede tratamento de
    # declaração aduaneira. Sobram os dois campos que a transportadora
    # realmente exige, sem rótulo que convide leitura extra.
    #
    # ⚠ Os dois vêm de FONTE ÚNICA em `services` (SHIPMENT_DESCRIPTION,
    # declared_value_usd) — aqui só se imprime. Nunca formatar `so.total_usd`
    # aqui: o valor declarado não é o da venda, e o porquê está na docstring.
    if doc.get('shipment_desc'):
        valor = doc.get('shipment_value')
        conteudo = Table(
            [[P(_t3('contents'), st_cap), P(_t3('declared'), st_cap)],
             [P(doc['shipment_desc'], st_shipn),
              P(f'USD {valor}' if valor is not None else '—', st_shipn)]],
            colWidths=[0.68 * avail, 0.32 * avail])
        conteudo.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, _INK),
            ('LINEAFTER', (0, 0), (0, -1), 0.4, _LINE),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (0, 0), 7),
            ('TOPPADDING', (0, 1), (-1, 1), 1),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story += [Spacer(0, 10), conteudo]

    # ── 4. Faixa de auditoria: fechamento + EMBARQUE ───────────────────────
    # O câmbio SAIU daqui em 2026-08-20 (dono): este documento deixou de ter
    # dinheiro de mercadoria, e taxa de conversão sem valor a converter é
    # ruído numa folha que a alfândega lê. Quem fechou e quando FICA — é a
    # procedência que sustenta a declaração de "testado e classificado" do
    # anexo. Entraram transportadora, rastreio e data do envio, que é o que a
    # transportadora procura primeiro.
    meta = [(_t3('issued'),    _fmt_dt(doc['issued_at'])),
            (_t3('closed'),    _fmt_dt(doc['closed_at'], com_hora=True)),
            (_t3('closed_by'), doc['closed_by'] or '—')]
    story += [Spacer(0, 10), _limpa(Table(
        [[P(k, st_cap) for k, _v in meta],
         [P(v, st_val) for _k, v in meta]],
        colWidths=[0.34 * avail, 0.36 * avail, 0.30 * avail]),
        [('BOTTOMPADDING', (0, 0), (-1, 0), 2),
         ('RIGHTPADDING', (0, 0), (-1, -1), 6)])]

    if doc.get('carrier') or doc.get('tracking') or doc.get('shipped_at'):
        envio = [(_t3('carrier'),    doc.get('carrier') or '—'),
                 (_t3('tracking'),   doc.get('tracking') or '—'),
                 (_t3('shipped_on'), _fmt_dt(doc.get('shipped_at')))]
        story += [Spacer(0, 7), _limpa(Table(
            [[P(k, st_cap) for k, _v in envio],
             [P(v, st_val) for _k, v in envio]],
            colWidths=[0.34 * avail, 0.36 * avail, 0.30 * avail]),
            [('BOTTOMPADDING', (0, 0), (-1, 0), 2),
             ('RIGHTPADDING', (0, 0), (-1, -1), 6)])]

    # ── 5. Tabelas ─────────────────────────────────────────────────────────
    def _grid(cabecalho, corpo, widths, alinhar_a_partir_de=1):
        data = [[P(h, st_th) for h in cabecalho]] + corpo
        last = len(data) - 1
        styles = [('BACKGROUND', (0, i), (-1, i), _ZEBRA)
                  for i in range(1, last) if i % 2 == 0]
        styles += [('FONT', (0, last), (-1, last), bold, 8.5, 10),
                   ('LINEABOVE', (0, last), (-1, last), 0.8, _INK)]
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), font, 8, 9.6),
            ('TEXTCOLOR', (0, 0), (-1, -1), _INK),
            ('ALIGN', (alinhar_a_partir_de, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, _INK),
            ('LINEBELOW', (0, 1), (-1, -2), 0.4, _LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ] + styles))
        return t

    def _money(valor, prefixo):
        return f'{prefixo} {valor}' if valor is not None else '—'

    # ── 5. A ÚNICA tabela: quantidade por categoria WTC ────────────────────
    # Dono, 2026-08-20: *"vamos tirar o detalhado por capacidade e preços deste
    # reporte, vai ficar unicamente a quantidade por categoria WTC, o resto é
    # tudo informação de despacho"*. Saíram as colunas de ¥/US$ e a tabela
    # inteira de "resumo por tipo de chip" (tipo × capacidade).
    #
    # Consequência que vale dizer alto: o `with_prices` deixou de mudar este
    # documento. Admin e gerente recebem AGORA o MESMO papel — o que não é
    # perda de função, é o documento assumindo o que ele é. A barreira de
    # dinheiro continua estrutural: aqui não existe coluna de valor para
    # esconder.
    story += [Spacer(0, 13), P(_t3('wtc'), st_sec)]
    corpo = [[r['label'], str(r['qty'])] for r in doc['wtc']]
    if doc['unkeyed']:
        corpo.append([P(_t3('nocat'), st_td), str(doc['unkeyed'])])
    corpo.append([P(_t3('total'), st_tdb), str(doc['total_units'])])
    story.append(_grid([_t3('category'), _t3('qty')], corpo,
                       [0.78 * avail, 0.22 * avail]))

    # ── 6. ANEXO — declaração sobre a MERCADORIA ───────────────────────────
    # Vem DEPOIS da tabela de propósito: quem confere olha carga primeiro,
    # declaração depois.
    #
    # ⚠ O que este anexo é, e o que ele deixou de ser, está escrito por extenso
    # no comentário de `_ANEXO`. Em uma linha: ele declara o que a MERCADORIA
    # é — não resíduo, uso civil — e não diz UMA palavra sobre aduana, Macau,
    # venda, desembaraço ou exportação. Papel de remessa simples que cita
    # trâmite aduaneiro chama atenção para o trâmite aduaneiro.
    st_anx  = ParagraphStyle('anx', fontName=font, fontSize=7, leading=9.2,
                             textColor=_INK, leftIndent=-6, spaceAfter=4,
                             alignment=4)          # justificado
    # ⚠ O parágrafo CHINÊS sai à ESQUERDA, não justificado. Motivo prático: o
    # `_rich` parte o texto em runs (chinês na TTF, latino na Helvetica), e
    # cada troca de fonte vira uma oportunidade de quebra. Justificando, o
    # reportlab estica ESSAS folgas para fechar a linha e abre buracos de dois
    # centímetros em volta de cada "Y49", "A1181", "3A090" — o pico do operador
    # `Tw` chegou a 101 pt. Tipografia CJK não pede justificação: o ideograma
    # tem largura fixa e a coluna fecha sozinha.
    st_anx_zh = ParagraphStyle('anxzh', parent=st_anx, alignment=0)
    st_anxh = ParagraphStyle('anxh', fontName=bold, fontSize=7.5, leading=10,
                             textColor=_INK, leftIndent=-6, spaceBefore=6,
                             spaceAfter=2)
    story += [Spacer(0, 14), P(_t3('annex'), st_sec)]
    for chave, textos in _ANEXO:
        story.append(P(_t3(chave), st_anxh))
        for i, texto in enumerate(textos):
            story.append(P(texto, st_anx_zh if i == 1 else st_anx))

    footer_txt = (f"{doc['so_code']} · {doc['lot_code']} · "
                  f"{_t('generated')} · {_fmt_dt(date.today())}")

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_GREY)
        _draw_mixed(canvas, 14 * mm, 9 * mm, footer_txt, 6.5, font, cjk)
        canvas.setFont(font, 6.5)
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm,
                               str(canvas.getPageNumber()))
        canvas.setStrokeColor(_BLUE)
        canvas.setLineWidth(0.8)
        canvas.line(14 * mm, 11.2 * mm, A4[0] - 14 * mm, 11.2 * mm)
        canvas.restoreState()

    doc_tpl.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def cor_da_diferenca(delta):
    """``(fundo, régua, tinta)`` da caixa da DIFERENÇA, pelo SINAL do número.

    Pública e no nível do módulo de propósito: é a única REGRA do documento
    (o resto é desenho), e regra que mora dentro de uma função de 200 linhas
    que devolve bytes de PDF não tem como ser testada — só olhada.

    · ``None``  → cinza: não há esperado com que comparar, e uma caixa
      colorida afirmaria um julgamento que o documento não tem.
    · ``< 0``   → âmbar: o cliente recebeu MENOS do que fechou, e é a única
      linha do papel que ele vai querer explicada.
    · ``0`` ou ``> 0`` → verde.

    ⚠ Era âmbar em TODOS os casos até 2026-09-04. No design system âmbar é
    atenção — o documento pedia atenção justamente no caso em que bateu tudo
    certo, que é o caso mais comum.
    """
    if delta is None:
        return _T_SURF3, _T_LINE2, _T_MUTED
    if delta < 0:
        return _T_SAND, _T_AMBER40, _T_AMBER
    return _T_MINT, _T_GREEN50, _T_GREEN


def _t_up(chave) -> str:
    """``EXPECTED (預期)`` — o rótulo bilíngue com o inglês em CAIXA ALTA.

    É o `.rmx__l` do frontend: 800 de peso, `letter-spacing:.08em`,
    `text-transform:uppercase`. Só o latino sobe — ideograma não tem caixa, e
    forçar `.upper()` na string inteira não faria nada com ele além de gastar
    a intenção.
    """
    en, zh = _L[chave][0], _L[chave][1]
    return f'{en.upper()} ({zh})'


def render_result_pdf(doc: dict) -> bytes:
    """PDF do RESULTADO da compra — o comprador baixa e manda pro cliente
    (dono, 2026-08-18).

    É a prestação de contas: enviado × recusado × aceito, categoria por
    categoria, e o valor final. É o ÚNICO papel em que o cliente vê a recusa
    detalhada — por isso ele mostra as três quantidades lado a lado em vez de
    só o líquido: "recebi 3529 e paguei por 3400" sem dizer o que caiu não
    presta contas de nada.

    ``doc`` = ``vendas.services.result_document(so, invoice)`` — dicionário
    pronto, sem banco aqui (mesmo contrato dos outros dois renders).

    Bilíngue inglês (繁體) como os demais: quem lê do outro lado é o Wu Quan.

    ── DESENHO: O PAPEL É A TELA (dono, 2026-09-04) ─────────────────────────

    *"Lembra que o PDF tem que parecer tipo o frontend, para criarmos um
    padrão visual fácil de distinguir em qualquer lugar"* — e é isso que
    governa cada decisão aqui. Não é "inspirado no": os valores saem do
    `tokens/colors.css` e as formas saem dos componentes que a ficha usa.

      · O BLOCO DE RESULTADO é o `.rmx--hero`: rótulo em caixa alta de peso
        800 com tracking, valor grande embaixo, e o que separa uma coluna da
        outra é um FIO de 1px sobre branco — `.rhead__mx` usa `gap:1px` com
        `background:var(--line)`, que desenha exatamente isso. Sem caixa e sem
        fundo: as três caixas coloridas que existiam aqui não vinham de
        componente nenhum (dono: "mt feio").
      · A COR vem dos modificadores: `.rmx--est` é `--ink-70`, `.rmx--res` é
        `--blue-70`, `.rmx--due` é `--amber-70` e `.rmx--ok` é `--green-70`.
      · O DINHEIRO é o par US$/¥ da tela do comprador: dólar na frente, ¥
        apagado embaixo — "o que ele vai pagar de fato".
      · A TABELA é a `.dtab`: cabeçalho `--ink-90` com texto branco, faixa de
        marca em `--ink-10`, fio entre linhas e nenhuma zebra.

    ⚠ ALINHAMENTO: as colunas numéricas usam estilo de parágrafo PRÓPRIO com
      `alignment=2`. O `('ALIGN', ...)` do TableStyle **não atravessa um
      Paragraph** — é a mesma armadilha do `TEXTCOLOR`, e a primeira versão
      desta tela saiu com os números encostados à esquerda, onde a comparação
      de grandeza que a coluna existe para permitir simplesmente não acontece.

    ⚠ AS FONTES CONTINUAM Helvetica/Courier, e é decisão consciente. As do
      design system (Manrope + IBM Plex Mono) não moram no repositório — o
      navegador as busca no Google Fonts, o que não existe num PDF. Embuti-las
      significa commitar os TTF e mexer no `_rich`/`_draw_mixed`, que fatiam
      os trechos CJK assumindo a Helvetica como base. É entrega própria.

    ⚠ Os outros dois documentos (packing list e o do gerente) seguem nos
      cinzas antigos, de propósito: vão para transportadora e alfândega, e
      restilizá-los de carona não é escopo — é efeito colateral.
    """
    font, bold, mono = 'Helvetica', 'Helvetica-Bold', _mono_font()
    cjk = _cjk_font(force=True)
    buf = BytesIO()
    doc_tpl = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=16 * mm,
        title=f"{doc['lot_code']} · {_L['result'][0]}", author='WhatTheChip')
    avail = A4[0] - 28 * mm

    DIR = 2   # alignment=2 → à direita. Coluna de número exige.

    st_cap = ParagraphStyle('cap', fontName=bold, fontSize=6.5, leading=9,
                            textColor=_T_MUTED)
    st_cap_r = ParagraphStyle('capr', parent=st_cap, alignment=2)
    # O TÍTULO do documento, no lugar onde ficava o código do lote (dono,
    # 2026-09-04). O lote não some da vida — ele está no rodapé de toda
    # página e é a chave que o cliente usa para achar o papel depois. O que
    # sai é a DUPLICATA dele no topo, ocupando o lugar mais nobre da folha
    # para dizer um número que ninguém procura antes de saber o que é o papel.
    st_title = ParagraphStyle('title', fontName=bold, fontSize=21, leading=25,
                              textColor=_T_INK)
    # ⚠ Helvetica, não mono (dono, 2026-09-04). O código da OV é o único
    # identificador que sobrou no topo, e em Courier ele lia como saída de
    # terminal, não como número de documento.
    st_code = ParagraphStyle('code', fontName=bold, fontSize=15, leading=18,
                             textColor=_T_INK, alignment=2)
    st_sub = ParagraphStyle('sub', fontName=font, fontSize=8, leading=11,
                            textColor=_T_MUTED)
    st_sec = ParagraphStyle('sec', fontName=bold, fontSize=8.5, leading=11,
                            textColor=_T_INK, spaceAfter=4)
    # O `.dtab th` da tela: mono do design system, CAIXA ALTA, uma linha só.
    #
    # ⚠ O reportlab NÃO tem `nowrap`. O que garante a linha única é a medição
    #   das `larguras` lá embaixo, e não este estilo — `splitLongWords=0` só
    #   impede quebra DENTRO de uma palavra, e o rótulo tem um espaço no meio.
    #   Quem segura isso de verdade é o `test_cada_rotulo_cabe_na_coluna_medida`.
    st_th = ParagraphStyle('th', fontName=mono, fontSize=6.5, leading=8,
                           textColor=colors.white, splitLongWords=0)
    st_th_r = ParagraphStyle('thr', parent=st_th, alignment=DIR)
    # ⚠ PELA QUARTA VEZ o mesmo tropeço: o `('TEXTCOLOR', (3,0), (3,0), ...)`
    # que morava no TableStyle NUNCA pintou nada — o TableStyle não atravessa
    # um Paragraph, e o `textColor=colors.white` do `st_th` vencia sempre. Os
    # dois rótulos saíam brancos desde a primeira versão. A cor tem de morar
    # no estilo do parágrafo, e é a mesma da tela:
    #   .dtab th.hr{color:var(--red-50)}  ·  .dtab th.hg{color:var(--green-40)}
    st_th_rej = ParagraphStyle('threj', parent=st_th_r, textColor=_T_RED50)
    st_th_ace = ParagraphStyle('thace', parent=st_th_r, textColor=_T_GREEN40)
    st_td = ParagraphStyle('td', fontName=font, fontSize=8, leading=9.6,
                           textColor=_T_INK)
    st_td_r = ParagraphStyle('tdr', parent=st_td, alignment=DIR)
    st_tdb = ParagraphStyle('tdb', fontName=bold, fontSize=8.5, leading=10,
                            textColor=_T_INK)
    st_tdb_r = ParagraphStyle('tdbr', parent=st_tdb, alignment=DIR)
    st_band = ParagraphStyle('band', fontName=bold, fontSize=8.5, leading=10.5,
                             textColor=_T_INK)
    st_band_r = ParagraphStyle('bandr', parent=st_band, alignment=DIR)
    st_dim = ParagraphStyle('dim', fontName=font, fontSize=8, leading=9.6,
                            textColor=_T_FAINT)
    st_dim_r = ParagraphStyle('dimr', parent=st_dim, alignment=DIR)
    # ⚠ A cor da recusa mora no ESTILO DO PARÁGRAFO, não num `TEXTCOLOR` do
    # TableStyle: o TableStyle não atravessa um Paragraph, e a primeira versão
    # saiu com as recusas pretas — iguais a qualquer outro número, sendo que é
    # a única coluna que o cliente vai querer discutir.
    st_rej_r = ParagraphStyle('rejr', fontName=bold, fontSize=8, leading=9.6,
                              textColor=_T_RED, alignment=DIR)
    st_band_rej = ParagraphStyle('bandrej', fontName=bold, fontSize=8.5,
                                 leading=10.5, textColor=_T_RED,
                                 alignment=DIR)

    def P(txt, estilo):
        return Paragraph(_rich(str(txt), cjk), estilo)

    def P_marca(marca, quantas):
        """Nome da marca + a contagem de linhas dela, apagada.

        ⚠ A marcação entra DEPOIS do `_rich`, e não dentro dele: o `_rich`
        escapa a string inteira (é o que salva marca com "&" no nome), então
        markup entregue a ele sai impresso como TEXTO. A primeira versão desta
        faixa escreveu `<font color='#878d96'>· 4</font>` na cara do cliente,
        e só o PDF de amostra pegou.
        """
        return Paragraph(
            _rich(str(marca), cjk)
            + " <font size='7' color='#878d96'>· %d</font>" % quantas,
            st_band)

    def _num(valor):
        """1146480.00 → 1,146,480.00 (dono, 2026-09-04: "formate o USD
        corretamente").

        Separador de milhar em vírgula e decimal em ponto: é a convenção que
        o leitor deste papel usa (o documento é inglês/中文), e é a mesma dos
        outros números do sistema. Sem ela, `US$ 170137.63` obriga a contar
        casas com o dedo — e contar casa em documento de dinheiro é como se
        erra uma ordem de grandeza.

        ⚠ Vale para o ¥ TAMBÉM, embora o pedido tenha falado do dólar: um par
        com `US$ 170,137.63` em cima e `¥ 1146480.00` embaixo pareceria dois
        sistemas de escrita na mesma célula.
        """
        return f'{valor:,.2f}'

    def _money(valor, prefixo):
        return f'{prefixo} {_num(valor)}' if valor is not None else '—'

    def P_par(usd, rmb, estilo):
        """O par US$/¥ na MESMA célula — o mesmo desenho da tela do comprador
        (dono, 2026-09-04: "mostra o preço em USD também na tabela, assim como
        mostra pro comprador").

        Dólar na frente porque é o que ele paga; ¥ embaixo, apagado, porque é
        a moeda em que a compra foi fechada e a que o cliente lê. Coluna nova
        para o dólar faria nove colunas numa tabela que já apertava.
        """
        txt = _rich(_money(usd, 'US$'), cjk)
        if rmb is not None:
            txt += ("<br/><font size='7' color='#878d96'>"
                    + _rich(_money(rmb, '¥'), cjk) + "</font>")
        return Paragraph(txt, estilo)

    def _limpa(tabela, styles=()):
        tabela.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ] + list(styles)))
        return tabela

    story = []

    # ── Cabeçalho: as duas marcas, o lote e a referência ───────────────────
    wtc_logo = _img(_WTC_LOGO)
    cli_logo = _img(doc.get('company_logo')) if doc.get('company_logo') else None
    if cli_logo is not None:
        cli_logo.hAlign = 'RIGHT'
    if wtc_logo or cli_logo:
        story += [_limpa(Table([[wtc_logo or '', cli_logo or '']],
                               colWidths=[0.5 * avail, 0.5 * avail]),
                         [('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]),
                  Spacer(0, 15)]

    # ⚠ O que o papel É, em corpo de título, e à direita o ÚNICO identificador
    # que o topo precisa (dono, 2026-09-04). O número da FATURA continua fora:
    # é papel interno do WhatTheChip e não diz nada a quem recebe (2026-08-18).
    # O código do LOTE segue no rodapé de todas as páginas.
    # ⚠ O rótulo e o código no MESMO bloco, e não em linhas separadas da
    # tabela de fora (dono, 2026-09-04: "esse topo aqui ficou meio torto").
    #
    # A geometria estava certa — medi: as baselines do título e do código
    # batiam com 0,24pt de diferença e as três bordas direitas fechavam em
    # 555,59, o milímetro exato da margem. O que estava errado era
    # PROXIMIDADE: o código desce para alinhar a baseline com o título de
    # 21pt, e o rótulo, preso na linha de cima da tabela, ficava para trás —
    # a 11pt do logo acima e a 16pt do número que ele rotula. Rótulo mais
    # perto de outra coisa do que do próprio valor agrupa com a coisa errada,
    # e o olho lê isso como desalinho antes de conseguir nomear o motivo.
    #
    # No bloco aninhado os dois descem JUNTOS, e a distância entre eles passa
    # a ser uma constante desta tabela, não uma sobra da altura do título.
    bloco_so = _limpa(Table(
        [[P(_t('so_result'), st_cap_r)],
         [P(doc['so_code'], st_code)]], colWidths=[0.44 * avail]),
        [('BOTTOMPADDING', (0, 0), (0, 0), 3)])
    story += [_limpa(Table(
        [[P(_t('result'), st_title), bloco_so]],
        colWidths=[0.56 * avail, 0.44 * avail]),
        # ⚠ O alinhamento horizontal mora no ESTILO DO PARÁGRAFO
        # (`alignment=2`), não num ('ALIGN', ...) do TableStyle: o TableStyle
        # não atravessa um Paragraph. Terceira vez que a armadilha aparece
        # nesta tela — a vertical, essa sim, é do TableStyle.
        [('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
         ('BOTTOMPADDING', (0, 0), (-1, 0), 3)])]

    # ── Quem e quando ──────────────────────────────────────────────────────
    # ⚠ SEM o nome do comprador: este documento vai para o cliente, e de quem
    # o WhatTheChip compra é sigilo de negócio (dono, 2026-08-18).
    #
    # Sem painel cinza (dono, 2026-09-04: "tirar esse retângulo cinza"). O que
    # fecha o cabeçalho é a RÉGUA AZUL, e ela desceu para DEPOIS das
    # informações — antes cortava entre os códigos e as datas, separando duas
    # coisas que são o mesmo bloco de identificação.
    meta = [
        (_t('ship_from_r'), doc.get('company') or '—'),
        (_t('closed'), _fmt_dt(doc.get('closed_at'))),
        (_t('received'), _fmt_dt(doc.get('received_at'))),
        (_t('settled'), _fmt_dt(doc.get('settled_at'))),
        (_t('fx'), (f"1 ¥ = US$ {doc['fx_rate']}"
                    if doc.get('fx_rate') is not None else '—')),
        # ⚠ Esta terceira coluna da segunda linha era o buraco do bloco. A
        # origem cai exatamente nela (dono, 2026-09-04: "ao lado da exchange
        # rate, embaixo de box received") — sem mexer no grid nem empurrar
        # nada, porque o espaço já estava reservado.
        (_t('lot_origin'), doc.get('lot_origin') or '—'),
    ]
    # ⚠ O grid se monta a partir do `meta`, e não com índices escritos à mão:
    #   a versão anterior cravava `''` na terceira coluna da segunda linha, o
    #   que fez o `meta[5]` novo (a origem) ser montado e nunca desenhado.
    #   Campo a mais = uma linha no `meta`, e o grid acompanha.
    info = Table(
        [linha for i in (0, 3)
         for linha in ([P(r, st_cap) for r, _ in meta[i:i + 3]],
                       [P(v, st_tdb) for _, v in meta[i:i + 3]])],
        colWidths=[avail / 3.0] * 3)
    info.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, 0), 0),
        ('TOPPADDING', (0, 2), (-1, 2), 8),
        ('TOPPADDING', (0, 1), (-1, 1), 1),
        ('TOPPADDING', (0, 3), (-1, 3), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 3), (-1, 3), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # a régua fecha o cabeçalho INTEIRO
        ('LINEBELOW', (0, 3), (-1, 3), 1.2, _T_BLUE),
    ]))
    story += [Spacer(0, 10), info]

    # ── O RESULTADO, no TOPO ───────────────────────────────────────────────
    # Estas três colunas ficavam no FIM do documento, depois de 100 linhas de
    # detalhamento (dono, 2026-09-04). É a resposta da página: quem abre um
    # resultado quer saber quanto deu antes de saber de onde veio.
    #
    # Desenho do `.rmx--hero`: sem caixa, sem fundo — o que separa é um FIO,
    # que é o que o `.rhead__mx` faz com `gap:1px` sobre `var(--line)`.
    #
    # A cor da DIFERENÇA responde ao SINAL, e isso é correção, não enfeite:
    # ela era âmbar em qualquer caso, e âmbar no nosso sistema é atenção — o
    # documento pedia atenção justamente quando não havia nada a explicar.
    delta = doc.get('delta_rmb')
    _bg, _regua, dif_ink = cor_da_diferenca(delta)

    def _st_l(cor):
        return ParagraphStyle('l%s' % cor, fontName=bold, fontSize=7,
                              leading=10, textColor=cor)

    def _st_v(cor):
        return ParagraphStyle('v%s' % cor, fontName=bold, fontSize=17,
                              leading=21, textColor=cor)

    def _st_u(cor):
        return ParagraphStyle('u%s' % cor, fontName=bold, fontSize=10,
                              leading=13, textColor=cor)

    def _delta(valor, prefixo):
        if valor is None:
            return '—'
        sinal = '−' if valor < 0 else ('+' if valor > 0 else '')
        return f'{sinal}{prefixo} {_num(abs(valor))}'

    col = avail / 3.0
    valores = Table(
        [[P(_t_up('expected'), _st_l(_T_INK70)),
          P(_t_up('final'), _st_l(_T_BLUE70)),
          P(_t_up('difference'), _st_l(dif_ink))],
         # US$ NA FRENTE (dono, 2026-09-04): é a moeda em que o dinheiro
         # muda de mão. O ¥ desce para secundário — continua no papel porque
         # é a moeda em que a compra foi fechada e a que o cliente lê, mas
         # deixa de disputar a primeira leitura. Mesma hierarquia da tela.
         [P(_money(doc.get('order_usd'), 'US$'), _st_v(_T_INK)),
          P(_money(doc.get('total_usd'), 'US$'), _st_v(_T_BLUE70)),
          P(_delta(doc.get('delta_usd'), 'US$'), _st_v(dif_ink))],
         [P(_money(doc.get('order_rmb'), '¥'), _st_u(_T_FAINT)),
          P(_money(doc.get('total_rmb'), '¥'), _st_u(_T_FAINT)),
          P(_delta(delta, '¥'), _st_u(_T_FAINT))]],
        colWidths=[col, col, col])
    valores.setStyle(TableStyle([
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, _T_LINE),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('LEFTPADDING', (1, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-2, -1), 14),
        ('RIGHTPADDING', (-1, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, 0), 14),
        ('TOPPADDING', (0, 1), (-1, 1), 5),
        ('TOPPADDING', (0, 2), (-1, 2), 1),
        ('BOTTOMPADDING', (0, 0), (-1, 1), 0),
        ('BOTTOMPADDING', (0, 2), (-1, 2), 15),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story += [valores]

    # ── O DETALHAMENTO, agrupado por MARCA ─────────────────────────────────
    # As linhas já chegam ordenadas por marca (`result_document` faz
    # `order_by('brand')`), então o agrupamento é sequencial e não reordena
    # nada — se um dia a ordem mudar na origem, aqui aparece marca repetida em
    # faixas separadas, que é um defeito VISÍVEL, e não um total errado.
    # ── AS LARGURAS SÃO MEDIDAS, NÃO CHUTADAS (dono, 2026-09-04) ─────────
    # O pedido foi "que o texto nao overlape pra linha debaixo". O que fazia o
    # rótulo quebrar não era a fonte: era CATEGORY / REJECTED / ACCEPTED terem
    # 8 letras latinas + 2 ideogramas dentro de colunas de 0,10 — e a coluna
    # de CATEGORY, larga, existir para caber "B-06", quatro caracteres.
    #
    # Em mono a conta fecha e não é opinião: cada latino avança 0,6 × corpo e
    # cada ideograma 1,0 × corpo. A 6,5pt, "CATEGORY (類別)" pede 55,9pt e
    # "SENT (寄出)" pede 40,3. Somados os sete rótulos com o padding e o
    # conteúdo mais largo de cada coluna (o "US$ 1,146,480.00" do total manda
    # na última), o mínimo dá 0,899 da faixa útil — sobram 52pt, distribuídos
    # abaixo como folga.
    #
    #   coluna     mínimo   aqui     folga
    #   TYPE       0,141    0,195    conteúdo: "Toshiba-Kioxia · 12"
    #   CATEGORY   0,132    0,140    manda o rótulo, não o "B-06"
    #   SENT       0,101    0,105
    #   REJECTED   0,132    0,140
    #   ACCEPTED   0,132    0,140
    #   UNIT       0,105    0,110
    #   TOTAL      0,156    0,170    conteúdo: o dinheiro
    #
    # ⚠ Os rótulos são CONSTANTES — `_L` é sempre inglês + 中文, não passa por
    #   tradução —, então a conta não se mexe por idioma do usuário. Quem
    #   mexer no `_L` da tabela tem de refazer a medição: o teste
    #   `test_o_cabecalho_cabe_em_uma_linha_so` avisa.
    larguras = [0.195, 0.14, 0.105, 0.14, 0.14, 0.11, 0.17]
    assert abs(sum(larguras) - 1) < 1e-9, larguras
    widths = [f * avail for f in larguras]

    def _soma(itens, chave):
        return sum((i[chave] for i in itens if i.get(chave) is not None),
                   Decimal('0.00'))

    # `_t_up` e não `_t`: `text-transform:uppercase` é do `.dtab th` (dono,
    # 2026-09-04, "pode deixar tudo MAIÚSCULO?"). Só o latino sobe — ideograma
    # não tem caixa. Em monoespaçada a caixa alta não custa largura nenhuma,
    # então isto é de graça.
    dados = [[P(_t_up('type'), st_th), P(_t_up('category'), st_th),
              P(_t_up('sent'), st_th_r), P(_t_up('rejected'), st_th_rej),
              P(_t_up('accepted'), st_th_ace), P(_t_up('unit'), st_th_r),
              P(_t_up('total'), st_th_r)]]
    estilos_extra, linhas_de_total = [], []
    for marca, itens in groupby(doc['lines'], key=lambda r: r['brand']):
        itens = list(itens)
        g_rej = sum(i['rejected'] for i in itens)
        i_faixa = len(dados)
        dados.append([
            P_marca(marca, len(itens)), '',
            P(sum(i['sent'] for i in itens), st_band_r),
            P(f'−{g_rej}', st_band_rej) if g_rej else P('0', st_band_r),
            P(sum(i['accepted'] for i in itens), st_band_r), '',
            P_par(_soma(itens, 'total_usd') or None,
                  _soma(itens, 'total_rmb'), st_band_r)])
        linhas_de_total.append(i_faixa)
        estilos_extra += [
            ('BACKGROUND', (0, i_faixa), (-1, i_faixa), _T_SURF2),
            ('SPAN', (0, i_faixa), (1, i_faixa)),
            ('LINEABOVE', (0, i_faixa), (-1, i_faixa), 0.5, _T_LINE2),
        ]
        for it in itens:
            dados.append([
                P(f"{it['type']} {it['capacity']}", st_td),
                P(it['wtc'], st_dim),
                P(it['sent'], st_td_r),
                # recusa ZERO fica apagada: nesta coluna o zero é a boa
                # notícia e não pode ter o mesmo peso de um número que existe
                P(f"−{it['rejected']}", st_rej_r) if it['rejected']
                else P('0', st_dim_r),
                P(it['accepted'], st_td_r),
                P_par(it.get('unit_usd'), it['unit_rmb'], st_td_r),
                P_par(it.get('total_usd'), it['total_rmb'], st_td_r)])

    i_total = len(dados)
    dados.append([
        P(_t('total'), st_tdb), '', P(doc['sent'], st_tdb_r),
        P(f"−{doc['rejected']}", st_band_rej) if doc['rejected']
        else P('0', st_tdb_r),
        P(doc['accepted'], st_tdb_r), '',
        P_par(doc.get('total_usd'), doc.get('total_rmb'), st_tdb_r)])

    linhas_de_total.append(i_total)
    # ── A LINHA QUE SOMA, UM TOM ABAIXO (dono, 2026-09-04) ────────────────
    # A faixa da marca e o total geral repetem as tintas das duas colunas do
    # julgamento com um passo a mais de saturação. Sem isso, o subtotal de uma
    # marca tinha exatamente a mesma cor das linhas que ele soma, e num pacote
    # de 40 linhas o olho não distingue a conta do lançamento.
    tintas_de_total = [('BACKGROUND', (c, i), (c, i), cor)
                       for i in linhas_de_total
                       for c, cor in ((3, _T_ROSE_TOT), (4, _T_MINT_TOT))]

    tabela = Table(dados, colWidths=widths, repeatRows=1)
    tabela.setStyle(TableStyle([
        # cabeçalho ESCURO com texto branco: é o `.dtab th` do sistema, e é o
        # que faz a tabela do papel ser reconhecivelmente a mesma da tela
        ('BACKGROUND', (0, 0), (-1, 0), _T_INK90),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        # SEM zebra: o pacote separa linha com fio, não com faixa. Em 100
        # linhas a zebra vira textura e some como informação.
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, _T_LINE),
        ('SPAN', (0, i_total), (1, i_total)),
        ('LINEABOVE', (0, i_total), (-1, i_total), 1, _T_INK),
        ('TOPPADDING', (0, i_total), (-1, i_total), 6),
        ('BOTTOMPADDING', (0, i_total), (-1, i_total), 6),
    ] + estilos_extra + [
        # ── AS DUAS COLUNAS DO JULGAMENTO (dono, 2026-09-04) ──────────────
        # `.dtab tbody td.hr{background:var(--red-10)}` e `.hg{--green-10}`:
        # é a MESMA tinta que a tela do comprador usa nessas duas colunas, e o
        # papel passa a ser reconhecível pela cor antes da leitura.
        #
        # ⚠ Vêm DEPOIS do `estilos_extra` de propósito. A faixa de marca pinta
        # a linha inteira de `--ink-10`; declarada depois, ela cobriria a
        # tinta das colunas e a marca apareceria sem o verde e o vermelho que
        # todas as linhas dela têm. No reportlab, o último estilo vence.
        ('BACKGROUND', (3, 1), (3, -1), _T_ROSE),
        ('BACKGROUND', (4, 1), (4, -1), _T_MINT),
    ] + tintas_de_total))
    story += [Spacer(0, 4), P(_t('detail'), st_sec), tabela]

    # OBSERVAÇÕES — agora uma LISTA (spec §6.9): tudo que a conferência
    # escreveu, na ordem em que escreveu. Cada nota leva a data, porque num
    # documento que se discute depois "quando" é metade da informação. A
    # assinatura é sempre a mesma palavra: a autoria real não atravessa o
    # balcão, e ela nem chega aqui — o `result_document` só manda data e
    # texto (mascarado na origem, não no desenho).
    notas = doc.get('notes') or []
    if notas:
        story += [Spacer(0, 13), P(_t('notes'), st_sec)]
        for nota in notas:
            story += [P(f"{_t('checked_by')} · {_fmt_dt(nota['at'])}", st_tdb),
                      P(nota['text'], st_td),
                      Spacer(0, 6)]

    # ⚠ Data POR EXTENSO só aqui. O packing list e o documento do gerente
    #   seguem em dd/mm/aaaa de propósito: vão para transportadora e alfândega,
    #   onde o formato curto é o esperado, e mexer neles de carona não é
    #   escopo — é efeito colateral.
    footer_txt = (f"{doc['lot_code']} · {doc['so_code']} · "
                  f"{_t('generated')} · {_fmt_extenso(date.today())}")

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_T_FAINT)
        _draw_mixed(canvas, 14 * mm, 9 * mm, footer_txt, 6.5, font, cjk)
        canvas.setFont(font, 6.5)
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm,
                               str(canvas.getPageNumber()))
        canvas.setStrokeColor(_T_BLUE)
        canvas.setLineWidth(0.8)
        canvas.line(14 * mm, 11.2 * mm, A4[0] - 14 * mm, 11.2 * mm)
        canvas.restoreState()

    doc_tpl.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
