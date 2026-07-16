"""Catálogo de preços do comprador em PDF (F9, dono 2026-07-10).

O comprador baixa da home do /partner/ um PDF com TODAS as suas tabelas —
é o documento que ele repassa aos clientes dele, então o desenho persegue
duas coisas: CLAREZA e COMPACIDADE. Em vez de listar 600+ linhas, o layout
é a MATRIZ da planilha original (que o comprador e os clientes dele já
conhecem): uma seção por tipo, marcas nas colunas, capacidades nas linhas —
uma célula por preço.

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


def catalog_data(buyer, currency='usd'):
    """Estrutura pura do catálogo: ``(columns, sections)``.

    - ``columns``: nomes das listas, marcas em ordem alfabética e a genérica
      ("Outras marcas") por último — mesma ordem da sidebar do /partner/.
    - ``sections``: por kind (ordem da planilha), linhas (gen, tier) ascend.,
      cada linha com ``label`` e ``cells`` alinhadas às colunas; célula =
      ``('quoted', '6.00')`` | ``('no_buy', None)`` | ``('not_made', None)``
      | ``('unquoted', None)``.
    - ``currency`` (F10.6): ``'usd'`` = DERIVADO (¥ armazenado × taxa
      contratual ``buyer.fx_usd_rate``, 2 casas — o documento que circula em
      dólar); ``'rmb'`` = o ¥ armazenado cru, sem zeros à direita ('90').
    """
    lists = list(PriceList.all_companies.filter(buyer=buyer, active=True)
                 .select_related('brand').order_by('brand__name'))
    lists.sort(key=lambda pl: (pl.brand_id is None,
                               pl.brand.name if pl.brand_id else ''))
    columns = [pl.brand.name if pl.brand_id else _('Outras marcas')
               for pl in lists]
    col_idx = {pl.pk: i for i, pl in enumerate(lists)}

    # Uma query; monta o grid em memória (centenas de linhas, nada de N+1).
    grid = {}          # (kind, gen, tier_value, tier_unit) -> [cell] * n
    n = len(lists)
    rate = buyer.fx_usd_rate            # taxa CONTRATUAL (F10) — só p/ 'usd'
    for p in Price.all_companies.filter(price_list__in=lists):
        key = (p.kind, p.gen, p.tier_value, p.tier_unit)
        cells = grid.setdefault(key, [('unquoted', None)] * n)
        if p.status == STATUS_QUOTED:
            if currency == 'rmb':
                # ¥ armazenado, sem zeros à direita (o comprador pensa em ¥
                # redondo). ⚠ normalize() sem :f imprimiria 9E+1.
                cell = ('quoted', f'{p.price_min.normalize():f}')
            else:
                usd = (p.price_min * rate).quantize(Decimal('0.01'),
                                                    ROUND_HALF_UP)
                cell = ('quoted', f'{usd:.2f}')
        elif p.status == STATUS_NO_BUY:
            cell = ('no_buy', None)
        elif p.status == STATUS_NOT_MADE:
            cell = ('not_made', None)
        else:
            cell = ('unquoted', None)
        cells[col_idx[p.price_list_id]] = cell

    sections = []
    for kind, _label in KIND_CHOICES:
        keys = sorted((k for k in grid if k[0] == kind),
                      key=lambda k: (k[1], k[2]))          # (gen, tier)
        if not keys:
            continue
        rows = []
        for _k, gen, tier, unit in keys:
            label = f'{gen} {_fmt_tier(tier)}{unit}' if gen \
                else f'{_fmt_tier(tier)}{unit}'
            rows.append({'label': label, 'cells': grid[(_k, gen, tier, unit)]})
        # eMCP/uMCP: a chave é por NAND (regra do comprador) — o título avisa.
        title = _KIND_LABEL[kind]
        if kind in ('emcp', 'umcp'):
            title += ' · NAND'
        sections.append({'title': title, 'rows': rows})
    return columns, sections


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


def render_catalog_pdf(buyer_name, columns, sections, currency='usd'):
    """Monta o PDF (bytes). Sem banco — recebe a estrutura de catalog_data.
    ``currency`` (F10.6) decide título/legenda/prefixo das células — os
    VALORES já vêm prontos na moeda certa de catalog_data.

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

    label_w = 0.16 * avail
    data_w = (avail - label_w) / max(len(columns), 1)
    head = [''] + [Paragraph(_rich(c, cjk), st_th) for c in columns]

    for sec in sections:
        story.append(Paragraph(sec['title'], st_sec))
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
        t.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), font, 7, 8.4),
            ('FONT', (0, 1), (0, -1), bold, 7, 8.4),      # rótulos de linha
            ('TEXTCOLOR', (0, 0), (-1, -1), _INK),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, _LINE),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, _INK),
            ('TOPPADDING', (0, 0), (-1, -1), 1.6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.6),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
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
