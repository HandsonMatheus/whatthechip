"""PDF da Ordem de Venda (F11.2c — dono: "simples, sem timbre").

Padrão do pricing/pdf.py (reportlab platypus, i18n eager sob o idioma da
sessão, dinheiro com ponto). Reusa os helpers CJK de lá (fonte embutida por
RUN — pegadinhas 1-3 do F9 já resolvidas). O nome do comprador NÃO aparece
(sigilo de plataforma). Sem banco aqui: recebe as linhas prontas da view.
"""

from datetime import date
from io import BytesIO
from pathlib import Path

from django.utils.translation import gettext as _

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Helpers CJK compartilhados (F9): fonte TTF embutida + runs por trecho.
from pricing.pdf import _cjk_font, _draw_mixed, _rich

_INK = colors.HexColor('#161616')
_GREY = colors.HexColor('#8d8d8d')
_LINE = colors.HexColor('#d0d0d0')
_ZEBRA = colors.HexColor('#f4f4f4')
_BLUE = colors.HexColor('#0f62fe')


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
    'so':         ('Sales order',          '銷售訂單'),
    'lot':        ('Lot',                  '批次'),
    'doc':        ('Lot check',            '批次核對'),
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
    'total_rmb':  ('Total ¥',              '總計 ¥'),
    'total_usd':  ('Total US$',            '總計 US$'),
    'generated':  ('Generated by WhatTheChip', '由 WhatTheChip 產生'),
    # ── Declaração aduaneira do embarque (dono, 2026-08-18) ────────────────
    'customs':    ('Customs declaration',  '報關申報'),
    'contents':   ('Description of contents', '內容物描述'),
    'declared':   ('Declared value',       '申報價值'),
    # ── Documento do RESULTADO (dono, 2026-08-18) ──────────────────────────
    'result':     ('Purchase result',      '採購結果'),
    'expected':   ('Expected',             '預期'),
    'final':      ('Final',                '最終'),
    'difference': ('Difference',           '差額'),
    'received':   ('Box received on',      '收貨日期'),
    'settled':    ('Result closed on',     '結果確認日期'),
    'sent':       ('Sent',                 '寄出'),
    'rejected':   ('Rejected',             '拒收'),
    'accepted':   ('Accepted',             '接收'),
    'brand':      ('Brand',                '品牌'),
    'notes':      ('Notes',                '備註'),
}


def _t(chave) -> str:
    """``Issued on (簽發日期)`` — o rótulo bilíngue de ``chave``.

    TODO rótulo do documento passa por aqui: título, legenda e cabeçalho de
    coluna (pedido do dono, 2026-08-18 — "ao lado de cada título, de cada
    campo, entre parênteses a tradução em chinês tradicional"). Não crie
    variante "só inglês" para caber numa coluna: aumente a coluna.
    """
    en, zh = _L[chave]
    return f'{en} ({zh})'


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
    """PDF do LOTE — conferência + embarque.

    Não é o PDF comercial com os números tampados: é outro documento. Quando
    ``doc['with_prices']`` é falso **nenhuma coluna de dinheiro existe** (nem
    mascarada) — a barreira é ESTRUTURAL, não há string de valor a vazar por
    bug de template. Com preço, as MESMAS tabelas ganham ¥/US$.

    ``doc`` = ``vendas.services.manager_document(so, with_prices=…)`` —
    dicionário pronto, sem banco aqui (mesmo contrato do ``render_so_pdf``).

    ⚠ A tabela "por tipo de chip" mostra o rótulo REAL ao lado do código de
    caixa: afrouxamento da F12 aprovado pelo dono em 2026-08-18 (ver o aviso
    em ``vendas/services.py``).
    """
    com_preco = bool(doc.get('with_prices'))
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

    # ── 2. Identificação: SO e LOTE, mesmo peso ─────────────────────────────
    story += [_limpa(Table(
        [[P(_t('so'), st_cap), P(_t('lot'), st_cap)],
         [P(doc['so_code'], st_code), P(doc['lot_code'], st_code)]],
        colWidths=[0.5 * avail, 0.5 * avail]),
        # ⚠ padding na LINHA inteira: diferente entre as duas legendas
        # desalinha as bases e um código parece "maior" que o outro.
        [('BOTTOMPADDING', (0, 0), (-1, 0), 1),
         ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
         ('LINEBELOW', (0, 1), (-1, 1), 1.2, _BLUE)])]

    estado = _L.get(doc['status'], _L['cancelled'])
    story += [Spacer(0, 4),
              P(f"{_t('doc')} · {estado[0]} ({estado[1]})", st_sub)]

    # ── 3. SHIP FROM × SHIP TO, lado a lado (leitura de transportadora) ─────
    def _caixa_endereco(chave, bloco):
        corpo = [P(_t(chave), st_cap)]
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
    if de or para:
        # Uma caixa só, dividida ao meio: o remetente à esquerda e o
        # destinatário à direita — o par que a transportadora procura junto.
        enderecos = Table(
            [[_caixa_endereco('ship_from', de) if de else '',
              _caixa_endereco('ship_to', para) if para else '']],
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

    # ── 3b. DECLARAÇÃO ADUANEIRA — exigência da transportadora ─────────────
    # Descrição e valor SEMPRE preenchidos (dono, 2026-08-18): campo em branco
    # é o que faz o pacote parar ou ser reavaliado por quem não conhece a
    # carga. O valor é FICTÍCIO e assumido como tal — é sucata para descarte,
    # e o valor comercial é justamente o que não pode viajar impresso na caixa.
    if doc.get('shipment_desc'):
        aduana = Table(
            [[P(_t('contents'), st_cap), P(_t('declared'), st_cap)],
             [P(doc['shipment_desc'], st_shipn),
              P(f"USD {doc.get('shipment_value', '')}", st_shipn)]],
            colWidths=[0.62 * avail, 0.38 * avail])
        aduana.setStyle(TableStyle([
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
        story += [Spacer(0, 8), P(_t('customs'), st_sec), aduana]

    # ── 4. Faixa de auditoria do fechamento ────────────────────────────────
    _fx = doc['fx_rate']
    meta = [(_t('issued'),    _fmt_dt(doc['issued_at'])),
            (_t('closed'),    _fmt_dt(doc['closed_at'], com_hora=True)),
            (_t('closed_by'), doc['closed_by'] or '—'),
            (_t('fx'), f'1 CNY = {_fx} USD' if _fx is not None else '—')]
    story += [Spacer(0, 10), _limpa(Table(
        [[P(k, st_cap) for k, _v in meta],
         [P(v, st_val) for _k, v in meta]],
        colWidths=[0.26 * avail, 0.28 * avail, 0.22 * avail, 0.24 * avail]),
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

    story += [Spacer(0, 13), P(_t('wtc'), st_sec)]
    if com_preco:
        cab = [_t('category'), _t('qty'), _t('unit_rmb'),
               _t('total_rmb'), _t('total_usd')]
        corpo = [[r['label'], str(r['qty']), _money(r['unit_rmb'], '¥'),
                  _money(r['total_rmb'], '¥'), _money(r['total_usd'], 'US$')]
                 for r in doc['wtc']]
        if doc['unkeyed']:
            corpo.append([P(_t('nocat'), st_td), str(doc['unkeyed']),
                          '—', '—', '—'])
        corpo.append([P(_t('total'), st_tdb), str(doc['total_units']), '',
                      _money(doc['total_rmb'], '¥'),
                      _money(doc['total_usd'], 'US$')])
        larguras = [0.28 * avail, 0.14 * avail, 0.17 * avail, 0.19 * avail,
                    0.22 * avail]
    else:
        cab = [_t('category'), _t('qty')]
        corpo = [[r['label'], str(r['qty'])] for r in doc['wtc']]
        if doc['unkeyed']:
            corpo.append([P(_t('nocat'), st_td), str(doc['unkeyed'])])
        corpo.append([P(_t('total'), st_tdb), str(doc['total_units'])])
        larguras = [0.78 * avail, 0.22 * avail]
    story.append(_grid(cab, corpo, larguras))

    story += [Spacer(0, 13), P(_t('spec'), st_sec)]
    corpo = [[r['type'], r['capacity'] or '—', str(r['qty'])]
             for r in doc['spec']]
    if doc['unkeyed']:
        corpo.append([P(_t('nocat'), st_td), '—', str(doc['unkeyed'])])
    corpo.append([P(_t('total'), st_tdb), '', str(doc['total_units'])])
    story.append(_grid([_t('type'), _t('capacity'), _t('qty')],
                       corpo,
                       [0.44 * avail, 0.32 * avail, 0.24 * avail],
                       alinhar_a_partir_de=2))

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
    """
    font, bold, mono = 'Helvetica', 'Helvetica-Bold', 'Courier-Bold'
    cjk = _cjk_font(force=True)
    buf = BytesIO()
    doc_tpl = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=16 * mm,
        title=f"{doc['lot_code']} · {_L['result'][0]}", author='WhatTheChip')
    avail = A4[0] - 28 * mm

    st_cap = ParagraphStyle('cap', fontName=bold, fontSize=7, leading=9.5,
                            textColor=_GREY)
    st_code = ParagraphStyle('code', fontName=mono, fontSize=14, leading=17,
                             textColor=_INK)
    st_sub = ParagraphStyle('sub', fontName=font, fontSize=8, leading=11,
                            textColor=_GREY, leftIndent=-6)
    st_sec = ParagraphStyle('sec', fontName=bold, fontSize=8.5, leading=11,
                            textColor=_INK, spaceAfter=3, leftIndent=-6)
    st_th = ParagraphStyle('th', fontName=bold, fontSize=7, leading=9,
                           textColor=_INK)
    st_td = ParagraphStyle('td', fontName=font, fontSize=8, leading=9.6,
                           textColor=_INK)
    st_tdb = ParagraphStyle('tdb', fontName=bold, fontSize=8.5, leading=10,
                            textColor=_INK)
    st_val = ParagraphStyle('val', fontName=bold, fontSize=13, leading=16,
                            textColor=_INK)

    def P(txt, estilo):
        return Paragraph(_rich(str(txt), cjk), estilo)

    def _limpa(tabela, styles=()):
        tabela.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ] + list(styles)))
        return tabela

    def _money(valor, prefixo):
        return f'{prefixo} {valor}' if valor is not None else '—'

    story = []

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

    # ⚠ LOTE e OV com o MESMO fontSize — o cliente procura pelo lote, o
    # comprador pela OV; nenhum manda no outro. O número da FATURA não entra:
    # é papel interno do WhatTheChip e não diz nada a quem recebe (dono,
    # 2026-08-18).
    story += [_limpa(Table(
        [[P(_t('lot'), st_cap), P(_t('so'), st_cap)],
         [P(doc['lot_code'], st_code), P(doc['so_code'], st_code)]],
        colWidths=[0.5 * avail, 0.5 * avail]),
        [('BOTTOMPADDING', (0, 0), (-1, 0), 1),
         ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
         ('LINEBELOW', (0, 1), (-1, 1), 1.2, _BLUE)])]
    story += [Spacer(0, 4), P(_t('result'), st_sub)]

    # ── Quem e quando ──────────────────────────────────────────────────────
    # ⚠ SEM o nome do comprador: este documento vai para o cliente, e de quem
    # o WhatTheChip compra é sigilo de negócio (dono, 2026-08-18).
    meta = [
        (_t('ship_from'), doc.get('company') or '—'),
        (_t('closed'), _fmt_dt(doc.get('closed_at'))),
        (_t('received'), _fmt_dt(doc.get('received_at'))),
        (_t('settled'), _fmt_dt(doc.get('settled_at'))),
        (_t('fx'), (f"1 ¥ = US$ {doc['fx_rate']}"
                    if doc.get('fx_rate') is not None else '—')),
    ]
    def _meta_linha(itens):
        largura = avail / max(1, len(itens))
        return _limpa(Table(
            [[P(r, st_cap) for r, _v in itens],
             [P(v, st_tdb) for _r, v in itens]],
            colWidths=[largura] * len(itens)),
            [('BOTTOMPADDING', (0, 0), (-1, 0), 1),
             ('BOTTOMPADDING', (0, 1), (-1, 1), 6)])

    story += [Spacer(0, 11), _meta_linha(meta[:3]), _meta_linha(meta[3:])]

    # ── A tabela do resultado ──────────────────────────────────────────────
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

    story += [Spacer(0, 13), P(_t('result'), st_sec)]
    corpo = [[P(r['brand'], st_td), P(f"{r['type']} {r['capacity']}", st_td),
              r['wtc'], str(r['sent']), str(r['rejected']), str(r['accepted']),
              _money(r['unit_rmb'], '¥'), _money(r['total_rmb'], '¥')]
             for r in doc['lines']]
    corpo.append([P(_t('total'), st_tdb), '', '', str(doc['sent']),
                  str(doc['rejected']), str(doc['accepted']), '',
                  _money(doc['total_rmb'], '¥')])
    story.append(_grid(
        [_t('brand'), _t('type'), _t('category'), _t('sent'), _t('rejected'),
         _t('accepted'), _t('unit_rmb'), _t('total_rmb')],
        corpo,
        [0.15 * avail, 0.19 * avail, 0.11 * avail, 0.10 * avail, 0.11 * avail,
         0.11 * avail, 0.11 * avail, 0.12 * avail],
        alinhar_a_partir_de=3))

    # ── ESPERADO × FINAL, com a diferença explícita ────────────────────────
    # A divisão é o ponto do documento (dono, 2026-08-18): o cliente fechou o
    # lote esperando um número e recebeu outro — a DIFERENÇA é o que ele vai
    # querer explicado, e ela não pode ficar para o leitor calcular.
    def _delta(valor, prefixo):
        if valor is None:
            return '—'
        sinal = '−' if valor < 0 else ('+' if valor > 0 else '')
        return f'{sinal}{prefixo} {abs(valor)}'

    story += [Spacer(0, 14)]
    valores = Table(
        [[P(_t('expected'), st_cap), P(_t('final'), st_cap),
          P(_t('difference'), st_cap)],
         [P(_money(doc.get('order_rmb'), '¥'), st_val),
          P(_money(doc.get('total_rmb'), '¥'), st_val),
          P(_delta(doc.get('delta_rmb'), '¥'), st_val)],
         [P(_money(doc.get('order_usd'), 'US$'), st_tdb),
          P(_money(doc.get('total_usd'), 'US$'), st_tdb),
          P(_delta(doc.get('delta_usd'), 'US$'), st_tdb)]],
        colWidths=[0.34 * avail, 0.33 * avail, 0.33 * avail])
    valores.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, _INK),
        ('LINEAFTER', (0, 0), (-2, -1), 0.4, _LINE),
        ('BACKGROUND', (1, 0), (1, -1), _ZEBRA),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('TOPPADDING', (0, 1), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(valores)

    if doc.get('notes'):
        story += [Spacer(0, 11), P(_t('notes'), st_sec),
                  P(doc['notes'], st_td)]

    footer_txt = (f"{doc['lot_code']} · {doc['so_code']} · "
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
