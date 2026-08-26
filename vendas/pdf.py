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
# Fundos de leve para as duas caixas que o cliente procura primeiro no
# resultado (dono, 2026-08-19): o FINAL em azul, a DIFERENÇA em amarelo.
# Tons 10 do Carbon — claros o bastante para o texto preto continuar legível
# e para não virar borrão quando o PDF sai impresso em preto e branco.
_SKY  = colors.HexColor('#edf5ff')      # azul 10  → resultado final
_SAND = colors.HexColor('#fcf4d6')      # amarelo 10 → diferença


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
        # Esperado fica no papel branco (é a referência); o FINAL puxa o azul
        # e a DIFERENÇA o amarelo — as duas caixas que ele vai procurar.
        ('BACKGROUND', (1, 0), (1, -1), _SKY),
        ('BACKGROUND', (2, 0), (2, -1), _SAND),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('TOPPADDING', (0, 1), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(valores)

    # OBSERVAÇÕES — agora uma LISTA (spec §6.9): tudo que a conferência
    # escreveu, na ordem em que escreveu. Cada nota leva a data, porque num
    # documento que se discute depois "quando" é metade da informação. A
    # assinatura é sempre a mesma palavra: a autoria real não atravessa o
    # balcão, e ela nem chega aqui — o `result_document` só manda data e
    # texto (mascarado na origem, não no desenho).
    notas = doc.get('notes') or []
    if notas:
        story += [Spacer(0, 11), P(_t('notes'), st_sec)]
        for nota in notas:
            story += [P(f"{_t('checked_by')} · {_fmt_dt(nota['at'])}", st_tdb),
                      P(nota['text'], st_td),
                      Spacer(0, 5)]

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
