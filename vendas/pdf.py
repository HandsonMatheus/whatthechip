"""PDF da Ordem de Venda (F11.2c — dono: "simples, sem timbre").

Padrão do pricing/pdf.py (reportlab platypus, i18n eager sob o idioma da
sessão, dinheiro com ponto). Reusa os helpers CJK de lá (fonte embutida por
RUN — pegadinhas 1-3 do F9 já resolvidas). O nome do comprador NÃO aparece
(sigilo de plataforma). Sem banco aqui: recebe as linhas prontas da view.
"""

from datetime import date
from io import BytesIO

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


def render_so_pdf(so, rows, total_rmb, total_usd, fx_rate) -> bytes:
    """``rows`` = [{label, qty, unit_rmb, total_rmb, total_usd}] (strings já
    formatadas; sem-preço vem com unit_rmb=None e reason no label)."""
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
    sub = (f'{t_title} · {t_status} · {so.lot.code} · '
           f'{t_rate} 1 CNY = {fx_rate} USD · {t_issued} {issued}')

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
        if r['unit_rmb'] is not None:
            data.append([r['label'], r['qty'], f"¥ {r['unit_rmb']}",
                         f"¥ {r['total_rmb']}", f"US$ {r['total_usd']}"])
        else:
            data.append([r['label'], r['qty'], '—', '—', '—'])
            styles.append(('TEXTCOLOR', (2, i), (4, i), _GREY))
        if i % 2 == 0:
            styles.append(('BACKGROUND', (0, i), (-1, i), _ZEBRA))
    # Linha de total:
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
