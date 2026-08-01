"""Catálogo de preços do comprador em PDF (F9, dono 2026-07-10).

O comprador baixa da home do /partner/ um PDF com a tabela COMPLETA —
é o documento que ele repassa aos clientes dele, então o desenho persegue
duas coisas: CLAREZA e COMPACIDADE. O layout segue a CONVENÇÃO da
repactuação (2026-07-27), a mesma do painel por tipo:
- eMCP/uMCP/LPDDR (UNIFICADOS): tabela simples capacidade → preço único
  (todas as marcas); combos em FAIXA mín–máx.
- eMMC/UFS/DDR (POR MARCA): matriz — marcas nas colunas (só as que têm
  linha do tipo + "Outras marcas"), capacidades nas linhas.
- SSD (linear): uma linha "por GB", quando o contrato tem a taxa.

Separação deliberada em duas funções:
- ``catalog_data(buyer)``    → consulta o banco e devolve estrutura pura
  (colunas + seções); único ponto com ORM, roda sob o escopo do parceiro.
- ``render_catalog_pdf(...)`` → reportlab puro, SEM banco — testável em
  isolamento e reaproveitável (amostras, previews).

i18n: os textos usam ``gettext`` EAGER (resolvem na chamada) — a view
embrulha a geração em ``translation.override(lang)`` porque o catálogo tem
SELETOR DE IDIOMA próprio (decisão do dono: o comprador escolhe em que
língua manda pros clientes, independente da sessão). Specs (eMMC, LPDDR4X,
16GB…) são canônicas e NUNCA se traduzem (I18N.md). Para zh-hans a fonte
é a CID ``STSong-Light`` do reportlab (CJK sem arquivo de fonte).
"""

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import translation
from django.utils.translation import gettext as _

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .models import (KIND_CHOICES, Price, PriceList, STATUS_NO_BUY,
                     STATUS_NOT_MADE, STATUS_QUOTED)

#: Rótulo por kind; a ordem das SEÇÕES é a própria ordem de KIND_CHOICES
#: (a da planilha: gerenciada → DRAM → GPU), iterada direto em catalog_data.
_KIND_LABEL = dict(KIND_CHOICES)

# Símbolos dos estados na célula (têm que existir em WinAnsi E na CID CJK;
# por isso '×' U+00D7 e '—' U+2014 — '✗' U+2717 NÃO existe em Helvetica).
_SYM_NO_BUY, _SYM_NOT_MADE = '×', '—'

_INK = colors.HexColor('#161616')
_GREY = colors.HexColor('#8d8d8d')
_RED = colors.HexColor('#a2191f')
_LINE = colors.HexColor('#d0d0d0')
_ZEBRA = colors.HexColor('#f4f4f4')
_BLUE = colors.HexColor('#0f62fe')


def _fmt_tier(value):
    """Decimal → texto sem zeros à direita ('1', '1.5', '64').

    ⚠ ``normalize()`` sozinho imprime notação científica (64.0 → 6.4E+1);
    o ``:f`` força decimal (pegadinha já documentada no PRECIFICACAO §12)."""
    s = f'{value.normalize():f}'
    return s


#: Ordem das seções = a do PAINEL POR TIPO (views._NAV_KINDS; repactuação
#: 2026-07-27): combos+LPDDR unificados primeiro, depois os por-marca.
_SECTION_KINDS = ('emcp', 'umcp', 'lpddr', 'emmc', 'ufs', 'ddr')


def _money(mn, mx, currency, rate):
    """Valor pronto na moeda: ¥ inteiro/sem zeros ('90'; faixa '90–100' com
    en-dash, que EXISTE em WinAnsi) ou USD derivado 2 casas ('12.60')."""
    if currency == 'rmb':
        lo, hi = f'{mn.normalize():f}', f'{mx.normalize():f}'
    else:
        q = Decimal('0.01')
        lo = f'{(mn * rate).quantize(q, ROUND_HALF_UP):.2f}'
        hi = f'{(mx * rate).quantize(q, ROUND_HALF_UP):.2f}'
    return lo if lo == hi else f'{lo}\u2013{hi}'


def _cell(p, currency, rate):
    if p.status == STATUS_QUOTED:
        return ('quoted', _money(p.price_min, p.price_max, currency, rate))
    if p.status == STATUS_NO_BUY:
        return ('no_buy', None)
    if p.status == STATUS_NOT_MADE:
        return ('not_made', None)
    return ('unquoted', None)


def catalog_data(buyer, currency='usd'):
    """Estrutura pura do catálogo, na CONVENÇÃO da repactuação (2026-07-27).

    Devolve a LISTA DE SEÇÕES na ordem do painel (`_SECTION_KINDS` + SSD):
    - UNIFICADA (eMCP/uMCP/LPDDR): ``unified=True``, ``columns=[]``, rows
      ``{'label', 'cell'}`` — as linhas moram SÓ na lista genérica
      (unificação estrutural); a faixa dos combos vira ``'90–100'``.
    - POR MARCA (eMMC/UFS/DDR): ``unified=False``, ``columns`` SÓ com as
      marcas que têm linha do tipo (+ "Outras marcas" por último), rows
      ``{'label', 'cells'}`` alinhadas às colunas.
    - SSD (linear, sem grid): seção de UMA linha "por GB" quando o contrato
      tem ``ssd_rmb_per_gb``.

    ``currency`` (F10.6): ``'usd'`` = DERIVADO (¥ × ``fx_usd_rate``, 2
    casas); ``'rmb'`` = o ¥ armazenado, inteiro/sem zeros à direita.
    """
    from .models import UNIFIED_KINDS
    lists = list(PriceList.all_companies.filter(buyer=buyer, active=True)
                 .select_related('brand'))
    # PLANO_FX (2026-08-01): USD derivado pela taxa de MERCADO vigente
    # (mid-market diária); bootstrap contratual só com a FxRate vazia.
    from .engine import current_fx_rate
    rate = current_fx_rate(buyer)[0]
    por_kind = {}
    for p in (Price.all_companies.filter(price_list__in=lists)
              .select_related('price_list__brand')):
        por_kind.setdefault(p.kind, []).append(p)

    def _unified_section(title, prices):
        unifs = sorted((p for p in prices if p.price_list.brand_id is None),
                       key=lambda p: (p.gen, p.tier_value))
        return {'title': title, 'unified': True, 'columns': [],
                'rows': [{'label': (f'{p.gen} ' if p.gen else '')
                                   + f'{_fmt_tier(p.tier_value)}{p.tier_unit}',
                          'cell': _cell(p, currency, rate)} for p in unifs]}

    def _matrix_section(title, prices):
        pls = sorted({p.price_list for p in prices},
                     key=lambda pl: (pl.brand_id is None,
                                     pl.brand.name if pl.brand_id else ''))
        col_idx = {pl.pk: i for i, pl in enumerate(pls)}
        columns = [pl.brand.name if pl.brand_id else _('Outras marcas')
                   for pl in pls]
        grid = {}
        for p in prices:
            key = (p.gen, p.tier_value, p.tier_unit)
            cells = grid.setdefault(key, [('unquoted', None)] * len(pls))
            cells[col_idx[p.price_list_id]] = _cell(p, currency, rate)
        rows = [{'label': (f'{gen} ' if gen else '')
                          + f'{_fmt_tier(tv)}{tu}',
                 'cells': grid[(gen, tv, tu)]}
                for gen, tv, tu in sorted(grid, key=lambda k: (k[0], k[1]))]
        return {'title': title, 'unified': False, 'columns': columns,
                'rows': rows}

    sections = []
    for kind in _SECTION_KINDS:
        prices = por_kind.get(kind, [])
        if not prices:
            continue
        # eMMC DUAL (acordo 2026-08-01): duas seções — celular (unificado)
        # e PCB (por marca). O mesmo PN, dois preços; a origem é do LOTE.
        if kind == 'emmc':
            phone = [p for p in prices if p.origin == 'phone']
            pcb = [p for p in prices if p.origin == 'pcb']
            if phone:
                t = 'eMMC · ' + _('celular')
                sections.append(_unified_section(t, phone))
            if pcb:
                sections.append(_matrix_section('eMMC · PCB', pcb))
            continue
        title = _KIND_LABEL[kind]
        if kind in ('emcp', 'umcp'):
            title += ' · NAND'
        if kind in UNIFIED_KINDS:
            # Unificado: só a genérica (o portão do modelo garante que linha
            # de marca não existe; o filtro aqui é defensivo).
            unifs = sorted((p for p in prices
                            if p.price_list.brand_id is None),
                           key=lambda p: (p.gen, p.tier_value))
            rows = [{'label': (f'{p.gen} ' if p.gen else '')
                              + f'{_fmt_tier(p.tier_value)}{p.tier_unit}',
                     'cell': _cell(p, currency, rate)} for p in unifs]
            sections.append({'title': title, 'unified': True,
                             'columns': [], 'rows': rows})
            continue
        pls = sorted({p.price_list for p in prices},
                     key=lambda pl: (pl.brand_id is None,
                                     pl.brand.name if pl.brand_id else ''))
        col_idx = {pl.pk: i for i, pl in enumerate(pls)}
        columns = [pl.brand.name if pl.brand_id else _('Outras marcas')
                   for pl in pls]
        grid = {}
        for p in prices:
            key = (p.gen, p.tier_value, p.tier_unit)
            cells = grid.setdefault(key, [('unquoted', None)] * len(pls))
            cells[col_idx[p.price_list_id]] = _cell(p, currency, rate)
        rows = [{'label': (f'{gen} ' if gen else '')
                          + f'{_fmt_tier(tv)}{tu}',
                 'cells': grid[(gen, tv, tu)]}
                for gen, tv, tu in sorted(grid, key=lambda k: (k[0], k[1]))]
        sections.append({'title': title, 'unified': False,
                         'columns': columns, 'rows': rows})

    # SSD (linear, F12.20): não tem grid — a linha nasce da taxa contratual.
    if buyer.ssd_rmb_per_gb is not None:
        v = buyer.ssd_rmb_per_gb
        if currency == 'rmb':
            money = f'{v.normalize():f}'
        else:
            money = f'{(v * rate).quantize(Decimal("0.001"), ROUND_HALF_UP).normalize():f}'
        sections.append({'title': 'SSD', 'unified': True, 'columns': [],
                         'rows': [{'label': _('por GB'),
                                   'cell': ('quoted', money)}]})
    return sections


#: Fonte CJK EMBUTIDA (subset automático do reportlab → PDF continua pequeno).
#: ⚠ Duas pegadinhas testadas em 2026-07-10:
#:   1. A CID STSong-Light NÃO é embutida — some em leitor sem a fonte
#:      (WeChat/celular, exatamente onde o catálogo circula). Por isso a TTF.
#:   2. A DroidSansFallbackFull (TrueType, Apache-2.0 — LICENSE ao lado) é SÓ
#:      CJK: o cmap não tem latino, dígitos, nem '×'/'—'/'·'. Logo ela NUNCA
#:      é a fonte-base: Helvetica cobre latino/números/símbolos SEMPRE, e a
#:      CJK entra por RUN (``_rich``/``_draw_mixed``) só nos trechos chineses.
_CJK_TTF = Path(__file__).resolve().parent / 'fonts' / 'DroidSansFallbackFull.ttf'

#: Runs CJK (ideogramas + pontuação fullwidth ：，。e formas de largura cheia).
_CJK_RE = re.compile(r'([⺀-鿿豈-﫿　-〿＀-￯]+)')


def _cjk_font():
    """Nome da fonte CJK registrada, ou None fora de zh. TTF embutida;
    fallback defensivo na CID STSong-Light se o arquivo sumir."""
    lang = translation.get_language() or ''
    if not lang.startswith('zh'):
        return None
    if _CJK_TTF.exists():
        if 'WTC-CJK' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('WTC-CJK', str(_CJK_TTF)))
        return 'WTC-CJK'
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    return 'STSong-Light'


def _rich(text, cjk):
    """Markup de Paragraph com os runs CJK em <font> próprio (base Helvetica).
    Escapa XML ANTES (nome de marca pode ter '&'); &amp;/&lt; não têm CJK,
    então o split posterior não quebra as entidades."""
    esc = escape(text)
    if not cjk:
        return esc
    return ''.join(
        f'<font name="{cjk}">{part}</font>'
        if _CJK_RE.fullmatch(part) else part
        for part in _CJK_RE.split(esc) if part)


def _draw_mixed(canvas, x, y, text, size, base, cjk):
    """drawString com troca de fonte por run (o footer tem chinês + latino)."""
    for part in (_CJK_RE.split(text) if cjk else [text]):
        if not part:
            continue
        f = cjk if (cjk and _CJK_RE.fullmatch(part)) else base
        canvas.setFont(f, size)
        canvas.drawString(x, y, part)
        x += pdfmetrics.stringWidth(part, f, size)


def render_catalog_pdf(buyer_name, sections, currency='usd'):
    """Monta o PDF (bytes). Sem banco — recebe a estrutura de catalog_data.
    Cada seção traz as PRÓPRIAS colunas (convenção 2026-07-27): unificada =
    tabela simples capacidade → preço; por marca = matriz. ``currency``
    (F10.6) decide título/legenda/prefixo — os VALORES já vêm prontos.

    ⚠ i18n: os ``_()`` ficam FORA das f-strings de propósito — no Python 3.11
    o tokenizer vê a f-string como um token só e o extractor/portão
    (chips/i18n_source.py) não enxergaria os msgids lá dentro."""
    t_title = _('Tabela de preços')
    if currency == 'rmb':
        t_unit = _('Preços em ¥ (RMB) por chip (unitário).')
        cur_prefix, cur_tag = '¥ ', '¥ RMB'
    else:
        t_unit = _('Preços em USD por chip (unitário).')
        cur_prefix, cur_tag = 'US$ ', 'US$'
    t_no_buy = _('Não compro')
    t_unified = _('preço único para todas as marcas')
    t_not_made = _('Não fabricado')
    t_blank = _('em branco: ainda sem cotação')
    t_issued = _('Emitido em')
    t_by = _('Gerado por WhatTheChip')

    font, bold = 'Helvetica', 'Helvetica-Bold'   # base SEMPRE latina (nota ↑)
    cjk = _cjk_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm,
        title=f'{buyer_name} — {t_title}',
        author='WhatTheChip')
    avail = A4[0] - 24 * mm

    st_h1 = ParagraphStyle('h1', fontName=bold, fontSize=15, leading=18,
                           textColor=_INK)
    st_sub = ParagraphStyle('sub', fontName=font, fontSize=8, leading=11,
                            textColor=_GREY)
    st_sec = ParagraphStyle('sec', fontName=bold, fontSize=9, leading=12,
                            textColor=_INK, spaceBefore=7, spaceAfter=2)
    st_th = ParagraphStyle('th', fontName=bold, fontSize=6.6, leading=7.6,
                           textColor=_INK, alignment=1)   # center, quebra
    #                                                       "Toshiba-Kioxia"

    issued = date.today().strftime('%d/%m/%Y')
    legend = (f'{t_unit} '
              f'{_SYM_NO_BUY} {t_no_buy} · '
              f'{_SYM_NOT_MADE} {t_not_made} · '
              f'{t_blank}')

    story = [
        # Título com a MOEDA (F10.6): o mesmo comprador circula os dois PDFs —
        # tem que dar pra distinguir na primeira linha.
        Paragraph(_rich(f'{buyer_name} — {t_title} ({cur_tag})', cjk), st_h1),
        Paragraph(_rich(f'{t_issued} {issued} · {legend}', cjk), st_sub),
        Spacer(0, 4),
    ]

    base_style = [
        ('FONT', (0, 0), (-1, -1), font, 7, 8.4),
        ('TEXTCOLOR', (0, 0), (-1, -1), _INK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, _LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 1.6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.6),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]

    for sec in sections:
        title = sec['title'] + (f' — {t_unified}' if sec['unified'] else '')
        story.append(Paragraph(_rich(title, cjk), st_sec))

        if sec['unified']:
            # ── UNIFICADA: capacidade → preço único (sem colunas de marca) ──
            data, styles = [], []
            for r_i, row in enumerate(sec['rows']):
                state, value = row['cell']
                if state == 'quoted':
                    val = f'{cur_prefix}{value}'
                elif state == 'no_buy':
                    val = _SYM_NO_BUY
                    styles.append(('TEXTCOLOR', (1, r_i), (1, r_i), _RED))
                elif state == 'not_made':
                    val = _SYM_NOT_MADE
                    styles.append(('TEXTCOLOR', (1, r_i), (1, r_i), _GREY))
                else:
                    val = ''
                data.append([row['label'], val])
                if r_i % 2 == 1:
                    styles.append(('BACKGROUND', (0, r_i), (-1, r_i), _ZEBRA))
            t = Table(data, colWidths=[0.24 * avail, 0.24 * avail],
                      hAlign='LEFT')
            t.setStyle(TableStyle(base_style + [
                ('FONT', (0, 0), (0, -1), bold, 7, 8.4),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ] + styles))
            story.append(t)
            continue

        # ── POR MARCA: matriz com as colunas DA seção ──
        columns = sec['columns']
        label_w = 0.16 * avail
        data_w = (avail - label_w) / max(len(columns), 1)
        head = [''] + [Paragraph(_rich(c, cjk), st_th) for c in columns]
        data, styles = [head], []
        for r_i, row in enumerate(sec['rows'], start=1):
            line = [row['label']]
            for c_i, (state, value) in enumerate(row['cells'], start=1):
                if state == 'quoted':
                    # Moeda em cada célula (dono, 2026-07-10): o catálogo
                    # circula solto — o preço precisa gritar a moeda.
                    line.append(f'{cur_prefix}{value}')
                elif state == 'no_buy':
                    line.append(_SYM_NO_BUY)
                    styles.append(('TEXTCOLOR', (c_i, r_i), (c_i, r_i), _RED))
                elif state == 'not_made':
                    line.append(_SYM_NOT_MADE)
                    styles.append(('TEXTCOLOR', (c_i, r_i), (c_i, r_i), _GREY))
                else:
                    line.append('')
            data.append(line)
            if r_i % 2 == 0:
                styles.append(('BACKGROUND', (0, r_i), (-1, r_i), _ZEBRA))
        t = Table(data, colWidths=[label_w] + [data_w] * len(columns),
                  repeatRows=1)
        t.setStyle(TableStyle(base_style + [
            ('FONT', (0, 1), (0, -1), bold, 7, 8.4),      # rótulos de linha
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, _INK),
        ] + styles))
        story.append(t)

    footer_txt = f'{buyer_name} · {t_by} · {issued}'

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(_GREY)
        _draw_mixed(canvas, 12 * mm, 8 * mm, footer_txt, 6.5, font, cjk)
        canvas.setFont(font, 6.5)
        canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, str(canvas.getPageNumber()))
        canvas.setStrokeColor(_BLUE)
        canvas.setLineWidth(0.8)
        canvas.line(12 * mm, 10.2 * mm, A4[0] - 12 * mm, 10.2 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
