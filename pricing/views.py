"""
pricing/views.py — F6: o dashboard do COMPRADOR em /partner/ (PRECIFICACAO §7.1).

É o substituto definitivo da planilha: o comprador (Wuquan) loga, vê o que falta
cotar (as "células amarelas"), o que está velho, e edita os preços DELE — em
**¥ (RMB)**, a moeda em que ele pensa (F10, §12.18: o ¥ digitado é o que o
banco guarda; o USD é derivado pela taxa contratual) — sem jamais ver auditoria
(`updated_by`/`last_updated` são só do admin, §7).

Segurança (3 camadas):
  1. `partner_required`: conta EXTERNA — o vínculo é `Buyer.users`, não
     Membership. Membro da empresa (operador/gerente/admin) recebe 403 aqui;
     anônimo vai pro login.
  2. Toda query é filtrada pelo `request.buyer` (posse), e lista de outro
     comprador é 404 — nunca "esconder link".
  3. GUC do RLS (§12.4): parceiro NÃO tem Membership → o TenancyMiddleware não
     emite `app.company_id` → sob Postgres+RLS ele leria ZERO linhas. O
     decorator roda a view inteira dentro de `company_scope(buyer.company)`,
     que seta contextvar + GUC (com restauração).

Sem HTMX aqui de propósito: formulários simples + PRG (post/redirect/get) —
menos peças móveis numa tela que o comprador usa de longe, no ritmo dele.
"""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.http import require_POST

from tenancy.scope import company_scope

from .models import (Buyer, KIND_CHOICES, KIND_UNIT, KINDS, Price,
                     PriceChangeRequest, PriceList, PricingConfig,
                     STATUS_CHOICES, STATUS_NO_BUY, STATUS_NOT_MADE,
                     STATUS_QUOTED, STATUS_UNQUOTED)

#: Ordem de exibição das linhas (espelha a planilha: gerenciada → DRAM → GPU).
_KIND_ORDER = {k: i for i, (k, _) in enumerate(KIND_CHOICES)}
_KIND_LABEL = dict(KIND_CHOICES)


#: Estados de revisão já DECIDIDOS — o que vira notificação.
_DECIDIDOS = ('approved', 'rejected')


def _unseen_decisions(buyer):
    """🔔 Decisões (aprovado/rejeitado) de PREÇO que o parceiro ainda não viu."""
    return PriceChangeRequest.all_companies.filter(
        price__price_list__buyer=buyer,
        review_status__in=_DECIDIDOS, seen_by_partner=False)


def _unseen_rates(buyer):
    """🔔 O mesmo, para as TAXAS DE CONTRATO (SSD/K9).

    Duas consultas e não uma união: são tabelas diferentes por razão
    estrutural (SSD e K9 não têm linha de grade), e o badge só precisa de dois
    `count()`. Para o comprador, porém, **é um sino só** — ele pediu uma
    mudança de preço; de que tabela ela saiu é problema nosso.
    """
    from .models import RateChangeRequest
    return RateChangeRequest.all_companies.filter(
        buyer=buyer, review_status__in=_DECIDIDOS, seen_by_partner=False)


def partner_required(view_func):
    """Gate do parceiro: login + vínculo `Buyer.users` ativo (v1: o primeiro).

    Roda a view sob `company_scope(buyer.company)` — Camada A (contextvar) e
    Camada B (GUC do RLS) valem para a request inteira do parceiro. Também
    anexa `request.partner_unseen` (badge 🔔) e `request.buys_badge` (o
    contador do item Compras) — os dois em TODA página do parceiro, porque os
    dois vivem no cabeçalho e o cabeçalho é o mesmo em todas."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        buyer = (Buyer.all_companies.filter(users=request.user, active=True)
                 .select_related('company').first())
        if buyer is None:
            raise PermissionDenied(_(
                'Esta área é do comprador. Sua conta não está vinculada a '
                'nenhum comprador ativo.'))
        # Import local: `vendas.views_partner` importa DESTE módulo, e o
        # de topo fecharia o ciclo.
        from vendas.services import buys_badge
        request.buyer = buyer
        if buyer.company_id:
            with company_scope(buyer.company):
                request.partner_unseen = (_unseen_decisions(buyer).count()
                                          + _unseen_rates(buyer).count())
                request.buys_badge = buys_badge(buyer)
                return view_func(request, *args, **kwargs)
        request.partner_unseen = (_unseen_decisions(buyer).count()
                                  + _unseen_rates(buyer).count())
        request.buys_badge = buys_badge(buyer)
        return view_func(request, *args, **kwargs)   # comprador de plataforma (futuro)
    return _wrapped


def _stale_cutoff():
    return date.today() - timedelta(days=PricingConfig.get_config().staleness_days)


def _lists_with_stats(buyer):
    """Listas do comprador com contagens (total/pendentes) — alimenta a SIDEBAR
    de navegação (todas as páginas) e a tabela-resumo da home."""
    lists = list(PriceList.all_companies.filter(buyer=buyer, active=True)
                 .select_related('brand', 'inherits_from__brand')
                 .order_by('brand__name'))
    per_list = {}
    for r in (Price.all_companies.filter(price_list__buyer=buyer)
              .values('price_list_id', 'status')):
        d = per_list.setdefault(r['price_list_id'],
                                {'total': 0, 'pending': 0, 'quoted': 0})
        d['total'] += 1
        if r['status'] == STATUS_UNQUOTED:
            d['pending'] += 1
        elif r['status'] == STATUS_QUOTED:
            d['quoted'] += 1
    for pl in lists:
        pl.stats = per_list.get(pl.pk, {'total': 0, 'pending': 0, 'quoted': 0})
    # Genérica por último (a sidebar lista marcas primeiro).
    # Repactuação 2026-07-27: a GENÉRICA vem PRIMEIRO — é onde vivem os
    # preços UNIFICADOS (eMCP/uMCP/LPDDR), o coração da tabela nova.
    lists.sort(key=lambda pl: (pl.brand_id is not None,
                               pl.brand.name if pl.brand_id else ''))
    return lists


# ── Navegação POR TIPO (dono, 2026-07-27: "no menu lateral fica cada tipo") ──
# Correção do comprador 2026-08-01: eMMC/UFS também são UNIFICADOS (a
# planilha sempre disse — coluna Unified). Só DDR é por marca (matriz);
# SSD é linear ¥/GB (sem grid) — fora.
# Ordem = a do FLUXO DE TRIAGEM (spec v2 §3.2), nunca alfabética. K9 e SSD
# entraram em 2026-08-26 (decisão C3): existiam no motor e no catálogo desde
# julho, mas o comprador não tinha onde vê-los — o preço deles só se mexia
# pelo Django admin, e ele nem sabia qual era.
_NAV_KINDS = ('emcp', 'umcp', 'lpddr', 'emmc', 'ufs', 'ddr', 'k9', 'ssd')
_MATRIX_KINDS = ('ddr',)
#: Tipos SEM grade: o preço é uma TAXA DE CONTRATO no `Buyer`, não uma linha
#: de `Price`. SSD é linear (¥/GB + piso por peça, capacidades derivadas); K9
#: é um número só. Ver `RateChangeRequest`.
_RATE_KINDS = ('ssd', 'k9')


def _data_iso(txt):
    """`YYYY-MM-DD` → date, ou None. Data ilegível não levanta: o catálogo tem
    de sair mesmo com um campo mal preenchido — sem validade é melhor que sem
    catálogo, e a tela mostra o que ele escolheu."""
    try:
        return date.fromisoformat((txt or '').strip())
    except (TypeError, ValueError):
        return None


def _fx_info(buyer):
    """Carimbo da taxa p/ o header (PLANO_FX): mercado vivo + data."""
    from .engine import fx_display
    return fx_display(buyer)


def _travados(request):
    """A fila de cotação travada do comprador, UMA vez por request.

    A barra de tipos vive em toda tela de preço e o Resumo pede a mesma coisa
    duas vezes (a barra e a tabela). `blocked_quotes` re-resolve cotação viva
    de cada rascunho contra o grid — pagar isso duas vezes na mesma página
    seria desperdício silencioso.
    """
    fila = getattr(request, '_wtc_travados', None)
    if fila is None:
        from django.urls import reverse
        from vendas.services import blocked_quotes
        fila = blocked_quotes(request.buyer)
        # Cada célula da faixa é um LINK para a grade que resolve — fila sem
        # caminho é só má notícia. Tipo sem grade (SSD linear, K9 fixo) fica
        # sem link em vez de apontar para um 404: ele continua na fila,
        # porque esconder o que trava seria pior que não ter para onde ir.
        for t in fila['linhas']:
            t['url'] = (reverse('pricing:partner_kind', args=[t['kind']])
                        if t['kind'] in _NAV_KINDS else '')
            # O título da célula é o TIPO (a tabela que ele vai abrir) e a
            # linha exata vem em mono ao lado — a mesma hierarquia da barra.
            t['tipo'] = _KIND_LABEL.get(t['kind'], t['kind'])
        request._wtc_travados = fila
    return fila


def _kind_nav(request):
    """[(kind, label, lacunas, travados)] p/ a sidebar — DUAS contagens.

    Somar as duas apagaria justamente a diferença que importa (spec v2 §3.5):

    · **lacuna** (âmbar) — célula sem cotação numa caixa que ninguém está
      vendendo. Pode esperar.
    · **travado** (vermelho) — lote JÁ FECHADO que a plataforma não consegue
      precificar sem esta tabela. É fila de trabalho.

    O vermelho vem ANTES do âmbar na linha: é ele que decide em que ordem o
    comprador abre as tabelas hoje.
    """
    from django.db.models import Count
    pend = {d['kind']: d['n']
            for d in Price.all_companies
            .filter(price_list__buyer=request.buyer, status=STATUS_UNQUOTED)
            .values('kind').annotate(n=Count('id'))}
    # SSD e K9 não têm linha de `Price` para contar — a lacuna deles é a taxa
    # de contrato em branco. Zero ali seria dizer "tabela completa" para quem
    # não tem preço nenhum, que é o oposto da verdade.
    b = request.buyer
    if b.ssd_rmb_per_gb is None:
        pend['ssd'] = 1
    if b.k9_rmb_each is None:
        pend['k9'] = 1
    trav = _travados(request)['por_tipo']
    return [(k, _KIND_LABEL[k], pend.get(k, 0), trav.get(k, 0))
            for k in _NAV_KINDS]


def _rate_mensagens(request, enviados, erros):
    """A resposta do envio, uma só para as duas portas (grade e taxa).

    O comprador não sabe — nem precisa saber — que uma tela grava `Price` e a
    outra grava taxa de contrato. Duas frases diferentes para o mesmo ato
    fariam ele achar que uma das duas não foi moderada.
    """
    if enviados:
        messages.success(request, _(
            '%(n)s mudança(s) enviadas para REVISÃO do WhatTheChip — passam '
            'a valer após a aprovação.') % {'n': enviados})
    elif not erros:
        messages.info(request, _('Nada a enviar — nenhuma linha mudou.'))
    for e in erros:
        messages.error(request, e)


def _contrato_ctx(request, kind):
    """Contexto das telas SEM grade — SSD (linear) e K9 (um número).

    Aqui não há `Price`: o preço é taxa de contrato no `Buyer`, e o que a tela
    desenha é o VIGENTE mais, quando existe, o PEDIDO pendente ao lado. A
    regra da spec §3.4 vale igual: o número antigo continua valendo até a
    plataforma aprovar — quem lê preço lê o `Buyer`, nunca o pedido.
    """
    from .engine import ssd_piso_venceu, ssd_rmb
    from .models import RateChangeRequest
    from .pdf import SSD_CAPS, _ssd_cap_label
    b = request.buyer
    pedido = (RateChangeRequest.all_companies
              .filter(buyer=b, kind=kind,
                      review_status=RateChangeRequest.REVIEW_PENDING).first())

    def _n(v):
        """¥ sem zeros à direita — 0.100 vira 0.1, 18.00 vira 18. Formatado
        em PYTHON: `floatformat` ignora localize-off (pegadinha F10)."""
        return '' if v is None else f'{v.normalize():f}'

    ctx = {'contrato': True, 'rate_kind': kind, 'pedido': pedido,
           'rate_disp': _n(b.ssd_rmb_per_gb if kind == 'ssd'
                           else b.k9_rmb_each)}
    if kind != 'ssd':
        return ctx
    taxa, piso = b.ssd_rmb_per_gb, b.ssd_floor_rmb
    ctx['floor_disp'] = _n(piso)
    # As CAPACIDADES SÃO DERIVADAS (§3.2) — não são linhas, não se editam, e
    # é por isso que elas saem do servidor já calculadas pela MESMA função que
    # precifica o lote. Uma segunda conta no template seria a chance de a tela
    # e a compra discordarem.
    ctx['caps'] = [
        {'gb': gb, 'label': _ssd_cap_label(gb),
         'rmb': (f'{ssd_rmb(taxa, gb, piso):f}' if taxa is not None else None),
         'piso': taxa is not None and ssd_piso_venceu(taxa, gb, piso)}
        for gb in SSD_CAPS]
    return ctx


def _rate_post(request, kind):
    """O POST das telas sem grade: vira `RateChangeRequest`, nunca preço.

    Devolve (enviados, erros). Mesmo contrato do laço de `partner_kind_save`:
    campo vazio = TIRAR o preço (volta a sem cotação, com motivo), e nada
    mudou = nenhum pedido fantasma.
    """
    from .models import RateChangeRequest
    b, erros = request.buyer, []
    rotulo = _KIND_LABEL[kind]

    def _num(nome):
        """'' → None; vírgula normaliza para ponto (o comprador digita 0,42)."""
        raw = (request.POST.get(nome) or '').strip().replace(',', '.')
        if raw == '':
            return None, True
        try:
            v = Decimal(raw)
        except InvalidOperation:
            return None, False
        return (v, True) if v >= 0 else (None, False)

    taxa, ok_taxa = _num('rate')
    piso, ok_piso = (_num('floor') if kind == 'ssd' else (None, True))
    if not ok_taxa:
        erros.append(_('%(item)s: taxa ilegível — use números') % {'item': rotulo})
    if not ok_piso:
        erros.append(_('%(item)s: piso ilegível — use números') % {'item': rotulo})
    if erros:
        return 0, erros
    # Piso sem taxa não precifica nada — o max() nem roda. O modelo recusa, e
    # recusar aqui devolve a frase em vez do 500.
    if kind == 'ssd' and piso is not None and taxa is None:
        return 0, [_('%(item)s: piso sem ¥/GB não precifica nada — informe a '
                     'taxa') % {'item': rotulo}]
    velho_taxa = b.ssd_rmb_per_gb if kind == 'ssd' else b.k9_rmb_each
    velho_piso = b.ssd_floor_rmb if kind == 'ssd' else None
    if (taxa, piso) == (velho_taxa, velho_piso):
        return 0, []
    try:
        with transaction.atomic():
            RateChangeRequest.all_companies.update_or_create(
                buyer=b, kind=kind,
                review_status=RateChangeRequest.REVIEW_PENDING,
                defaults={'new_rate': taxa, 'new_floor': piso,
                          'old_rate': velho_taxa, 'old_floor': velho_piso,
                          'requested_by': request.user})
    except (ValidationError, IntegrityError):
        return 0, [_('%(item)s: conflito ao salvar — tente de novo')
                   % {'item': rotulo}]
    return 1, []


@partner_required
def partner_kind(request, kind):
    """Grid de UM TIPO de chip. Unificado (eMCP/uMCP/LPDDR): coluna única —
    linhas da genérica (faixa mín–máx nos combos). Por marca (eMMC/UFS/DDR):
    MATRIZ — linha = geração+faixa, coluna = marca (+ Outras); cada célula
    posta no partner_save da lista dela (moderação intacta)."""
    if kind not in _NAV_KINDS:
        from django.http import Http404
        raise Http404
    from .models import UNIFIED_KINDS

    def _fmt(v):
        return f'{v.normalize():f}' if v is not None else ''

    listas = list(PriceList.all_companies.filter(buyer=request.buyer,
                                                 active=True)
                  .select_related('brand'))
    generica = next((pl for pl in listas if pl.brand_id is None), None)
    pendentes = {
        r.price_id: r
        for r in PriceChangeRequest.all_companies.filter(
            price__price_list__buyer=request.buyer, price__kind=kind,
            review_status=PriceChangeRequest.REVIEW_PENDING)}

    # §3.5, terceira parada do caminho: quem chegou pela BARRA (e não pela
    # faixa do Resumo) não viu a fila. O aviso vermelho no topo e a marca na
    # linha exata existem para ele — sem isso o selo da barra manda o
    # comprador para uma tabela de trinta linhas sem dizer QUAL trava.
    trav_deste = [t for t in _travados(request)['linhas']
                  if t['kind'] == kind]
    trav_linha = {(t['kind'], t['gen'], t['tier_value'], t['tier_unit']):
                  t['orders'] for t in trav_deste}
    ctx = {'buyer': request.buyer, 'kind': kind,
           'kind_label': _KIND_LABEL[kind],
           'unified': kind in UNIFIED_KINDS,
           'ranged': kind in ('emcp', 'umcp'),
           'kind_nav': _kind_nav(request), 'active_kind': kind,
           'fx_info': _fx_info(request.buyer),
           'travados': trav_deste,
           'active_pk': None}

    # SSD e K9 saem por aqui: não têm `Price`, então nada abaixo (o grid
    # unificado, a matriz, a moderação por linha) se aplica a eles.
    if kind in _RATE_KINDS:
        ctx.update(_contrato_ctx(request, kind))
        return render(request, 'pricing/partner_kind.html', ctx)

    def _pend_disp(q):
        """Texto do pedido pendente, formatado em Python (floatformat
        ignora localize-off — pegadinha F10)."""
        if q is None:
            return None
        if q.new_status != STATUS_QUOTED:
            return q.get_new_status_display()
        txt = f'¥ {_fmt(q.new_price)}'
        if q.new_price_max is not None and q.new_price_max != q.new_price:
            txt += f'–{_fmt(q.new_price_max)}'
        return txt

    def _prep_unified(qs):
        rows = sorted(qs, key=lambda p: (p.gen, p.tier_value))
        for p in rows:
            p.pending = pendentes.get(p.pk)
            p.pend_disp = _pend_disp(p.pending)
            p.tier_disp = _fmt(p.tier_value)
            # Célula estilo PLANILHA (v3): número = ¥ · "x" = não compro ·
            # vazio = sem cotação; nos combos o máx tem campo próprio.
            p.cell_disp = ('x' if p.status == STATUS_NO_BUY
                           else _fmt(p.price_min)
                           if p.status == STATUS_QUOTED else '')
            p.maxin_disp = (_fmt(p.price_max)
                            if p.status == STATUS_QUOTED else '')
            # §3.5: na coluna Estado, `travando N pedidos` no lugar de
            # `Não cotado`. As duas são verdade — só uma explica a urgência.
            p.travado = trav_linha.get((p.kind, p.gen, p.tier_value,
                                        p.tier_unit), 0)
        return rows

    if kind in UNIFIED_KINDS:
        ctx.update({'rows': _prep_unified(Price.all_companies.filter(
            price_list=generica, kind=kind)), 'generica': generica})
        return render(request, 'pricing/partner_kind.html', ctx)

    if kind == 'emmc':
        # DUAL (acordo 2026-08-01): CELULAR = unificado (genérica, origin
        # phone) + PCB = matriz por marca (origin pcb). Mesma página, duas
        # seções; o batch save é por pk — cobre as duas sem mudança.
        from .models import ORIGIN_PCB, ORIGIN_PHONE
        ctx.update({'dual': True,
                    'rows': _prep_unified(Price.all_companies.filter(
                        price_list=generica, kind='emmc',
                        origin=ORIGIN_PHONE)),
                    'generica': generica})
        all_rows = list(Price.all_companies.filter(
            price_list__buyer=request.buyer, kind='emmc', origin=ORIGIN_PCB)
            .select_related('price_list__brand'))
    else:
        # matriz: colunas = marcas com linha deste tipo (+ Outras/genérica)
        all_rows = list(Price.all_companies.filter(
            price_list__buyer=request.buyer, kind=kind)
            .select_related('price_list__brand'))
    col_lists = sorted({p.price_list for p in all_rows},
                       key=lambda pl: (pl.brand_id is None,
                                       pl.brand.name if pl.brand_id else ''))
    chaves = sorted({(p.gen, p.tier_value, p.tier_unit) for p in all_rows},
                    key=lambda c: (c[0], c[1]))
    celulas = {(p.price_list_id, p.gen, p.tier_value): p for p in all_rows}
    linhas = []
    for gen, tier, unit in chaves:
        cells = []
        for pl in col_lists:
            p = celulas.get((pl.pk, gen, tier))
            if p is not None:
                p.pending = pendentes.get(p.pk)
                p.pend_disp = _pend_disp(p.pending)
                # Célula estilo PLANILHA (v2): número = ¥ · "x" = não compro ·
                # vazio = sem cotação (mesma convenção da planilha do comprador).
                p.cell_disp = ('x' if p.status == STATUS_NO_BUY
                               else _fmt(p.price_min)
                               if p.status == STATUS_QUOTED else '')
            cells.append((pl, p))
        # A matriz por marca não tem coluna Estado (cada célula é um campo),
        # então a marca vai no CABEÇALHO da linha — que é o que a spec chama
        # de "a linha exata". A trava é da LINHA, não de uma marca: o preço
        # que falta pode estar em qualquer coluna dela.
        linhas.append({'gen': gen, 'tier': _fmt(tier), 'unit': unit,
                       'cells': cells,
                       'travado': trav_linha.get((kind, gen, tier, unit), 0)})
    ctx.update({'linhas': linhas, 'col_lists': col_lists})
    return render(request, 'pricing/partner_kind.html', ctx)


@partner_required
def partner_home(request):
    """Home do parceiro: o RESUMO — pendências primeiro (mata a planilha) e a
    situação geral de todas as marcas de uma olhada."""
    buyer = request.buyer
    lists = _lists_with_stats(buyer)
    rows = Price.all_companies.filter(price_list__buyer=buyer)

    cutoff = _stale_cutoff()
    pending = rows.filter(status=STATUS_UNQUOTED).count()
    stale = (rows.filter(status=STATUS_QUOTED, quote_date__isnull=True).count()
             + rows.filter(status=STATUS_QUOTED, quote_date__lt=cutoff).count())
    quoted = rows.filter(status=STATUS_QUOTED).count()

    from django.db.models import Count
    por_kind = {}
    for d in rows.values('kind', 'status').annotate(n=Count('id')):
        por_kind.setdefault(d['kind'], {})[d['status']] = d['n']
    from .models import UNIFIED_KINDS
    nav = _kind_nav(request)
    kinds_resumo = [
        {'kind': k, 'label': lbl, 'unified': k in UNIFIED_KINDS,
         'dual': k == 'emmc',        # celular unificado × PCB por marca
         'quoted': por_kind.get(k, {}).get(STATUS_QUOTED, 0),
         'pending': pend,
         # §3.5: a coluna "Cotadas" diz `travando N pedidos` no lugar de
         # `N sem cotação` quando as duas coisas são verdade. As duas SÃO —
         # mas só uma explica a urgência, e é ela que o comprador precisa ler.
         'travados': trav}
        for k, lbl, pend, trav in nav]
    return render(request, 'pricing/partner_home.html', {
        'buyer': buyer, 'lists': lists, 'nav_lists': lists, 'active_pk': None,
        'kind_nav': nav, 'active_kind': None,
        'fx_info': _fx_info(buyer),
        'kinds_resumo': kinds_resumo,
        # A FAIXA da fila (§3.5). Some quando zera: não é painel, é fila.
        'fila': _travados(request),
        'pending': pending, 'stale': stale, 'quoted': quoted,
        'staleness_days': PricingConfig.get_config().staleness_days,
    })


@partner_required
def partner_list(request, list_pk):
    """Grid de edição de UMA lista — GRID UNIFICADO (decisão 2026-07-07): toda
    marca tem as MESMAS linhas (semeadas pelo `seed_price_grid`); nada de
    exibir herança aqui. Filtros por tipo e por estado via GET."""
    pl = get_object_or_404(
        PriceList.all_companies.filter(buyer=request.buyer)
        .select_related('brand'), pk=list_pk)

    f_kind = request.GET.get('kind', '')
    f_state = request.GET.get('state', '')
    qs = Price.all_companies.filter(price_list=pl)
    # Repactuação 2026-07-27 (ESTRUTURAL): kinds unificados (eMCP/uMCP/LPDDR)
    # vivem SÓ na genérica — aba de MARCA nem os oferece no filtro.
    from .models import UNIFIED_KINDS
    if pl.brand_id is not None:
        qs = qs.exclude(kind__in=UNIFIED_KINDS)
    if f_kind in KINDS:
        qs = qs.filter(kind=f_kind)
    if f_state in {s for s, _ in STATUS_CHOICES}:
        qs = qs.filter(status=f_state)

    rows = sorted(qs, key=lambda p: (p.kind not in UNIFIED_KINDS,
                                     _KIND_ORDER.get(p.kind, 99),
                                     p.gen, p.tier_value))
    # F6.1: mudanças EM REVISÃO — o parceiro precisa ver que o pedido existe
    # (o valor vigente só muda quando o admin aprovar).
    pendentes = {
        r.price_id: r
        for r in PriceChangeRequest.all_companies.filter(
            price__price_list=pl,
            review_status=PriceChangeRequest.REVIEW_PENDING)
    }
    for p in rows:
        p.kind_label = _KIND_LABEL.get(p.kind, p.kind)
        p.pending = pendentes.get(p.pk)
        p.unified = p.kind in UNIFIED_KINDS
        p.ranged = p.kind in ('emcp', 'umcp')   # únicos em FAIXA (2026-07-27)

    kind_choices = (KIND_CHOICES if pl.brand_id is None else
                    [(k, l) for k, l in KIND_CHOICES
                     if k not in UNIFIED_KINDS])
    return render(request, 'pricing/partner_list.html', {
        'buyer': request.buyer, 'price_list': pl, 'rows': rows,
        'f_kind': f_kind, 'f_state': f_state,
        'kind_choices': kind_choices, 'state_choices': STATUS_CHOICES,
        'nav_lists': _lists_with_stats(request.buyer), 'active_pk': pl.pk,
        'kind_nav': _kind_nav(request), 'active_kind': None,
        'fx_info': _fx_info(request.buyer),
    })


@partner_required
def partner_how(request):
    """'Como funciona' — guia CURTO do dashboard para o comprador (pedido do
    dono, 2026-07-09: comunicação objetiva, o comprador chinês não gosta de
    ler). Conteúdo 100% no template, marcado com {% trans %} (MULTILANGUAGE §7)."""
    return render(request, 'pricing/partner_how.html', {
        'buyer': request.buyer,
        'nav_lists': _lists_with_stats(request.buyer), 'active_pk': 'how',
        'kind_nav': _kind_nav(request), 'active_kind': None,
        'fx_info': _fx_info(request.buyer),
    })


#: Descrição curta por tipo, para a tela do Catálogo (§5.2: a busca é por
#: NOME **e descrição** — sem a descrição a busca só acha quem já sabe a sigla).
#: Canônicas na sigla, humanas no resto.
_KIND_DESC = {
    'emcp':  _lazy('combo NAND + LPDDR — preço por NAND, faixa mín–máx'),
    'umcp':  _lazy('combo UFS + LPDDR — preço por NAND, faixa mín–máx'),
    'lpddr': _lazy('LPDDR avulsa — preço unificado por geração'),
    'emmc':  _lazy('celular (unificado) × PCB (por marca)'),
    'ufs':   _lazy('armazenamento de celular — preço unificado'),
    'ddr':   _lazy('memória de PCB — matriz por marca'),
    'k9':    _lazy('NAND Samsung avulsa — preço único por unidade'),
    'ssd':   _lazy('preço linear ¥/GB, com piso por peça'),
}

#: Forma da tabela, como a spec §3.2 a nomeia. Vai na coluna "Estrutura" —
#: é o que explica por que um tipo tem 40 linhas e outro tem 1.
_KIND_FORM = {
    'emcp': _lazy('faixa mín–máx, uma coluna'),
    'umcp': _lazy('faixa mín–máx, uma coluna'),
    'lpddr': _lazy('unificada — uma coluna de preço'),
    'emmc': _lazy('celular × PCB — duas tabelas'),
    'ufs': _lazy('unificada — uma coluna de preço'),
    'ddr': _lazy('por marca — matriz'),
    'k9': _lazy('uma linha, um preço'),
    'ssd': _lazy('linear ¥/GB, com piso por peça'),
}


def _catalogo_tipos(buyer):
    """[{key, label, desc, form, lines, miss, quoted}] — o que a tela lista.

    ``lines`` NÃO conta ``not_made`` (spec §3.3: ausência de PRODUTO não é
    linha de preço; contá-la faria a cobertura mentir para baixo em todo tipo
    que tem célula não fabricada).

    SSD e K9 não têm linha de `Price`: a "tabela" deles é a taxa de contrato,
    então valem **uma** linha — e só quando ela existe. Sem taxa não há o que
    publicar (o gerador pula a seção), e oferecer o tipo mesmo assim seria uma
    caixinha que se marca e não muda o PDF: o rodapé contaria 8 de 8 tipos e
    sairiam 7 seções. Que a lacuna deles apareça é papel do RESUMO e do selo
    âmbar da barra; esta tela responde "o que vai no documento".
    """
    from django.db.models import Count
    por_kind = {}
    for d in (Price.all_companies
              .filter(price_list__buyer=buyer)
              .exclude(status=STATUS_NOT_MADE)
              .values('kind', 'status').annotate(n=Count('id'))):
        alvo = por_kind.setdefault(d['kind'], {'lines': 0, 'miss': 0})
        alvo['lines'] += d['n']
        if d['status'] == STATUS_UNQUOTED:
            alvo['miss'] += d['n']
    contratos = {'ssd': buyer.ssd_rmb_per_gb, 'k9': buyer.k9_rmb_each}
    out = []
    for k in _NAV_KINDS:
        if k in contratos:
            lines, miss = (0, 0) if contratos[k] is None else (1, 0)
        else:
            d = por_kind.get(k, {'lines': 0, 'miss': 0})
            lines, miss = d['lines'], d['miss']
        if not lines:
            continue                     # tipo sem tabela nenhuma não é opção
        out.append({'key': k, 'label': _KIND_LABEL[k],
                    'desc': _KIND_DESC.get(k, ''),
                    'form': _KIND_FORM.get(k, ''),
                    'lines': lines, 'miss': miss, 'quoted': lines - miss})
    return out


@partner_required
def partner_catalog(request):
    """A tela do CATÁLOGO (spec v2 §5.2) — o gerador do PDF que o comprador
    manda aos clientes dele.

    Antes o catálogo era um card na home com dois selects. Virou tela porque
    ganhou seis decisões (tipos, idioma, moeda, validade, lacunas, recado), e
    seis decisões num card viram um card que ninguém lê.

    **A seleção é por EXCLUSÃO, e isso é do servidor também**: a tela marca
    tudo, o POST manda os marcados, e a ausência do parâmetro no gerador
    significa TODOS. Assim um tipo novo entra no catálogo sozinho — ninguém
    precisa lembrar de marcá-lo.
    """
    buyer = request.buyer
    return render(request, 'pricing/partner_catalog.html', {
        'buyer': buyer,
        'tipos': _catalogo_tipos(buyer),
        'nav_lists': _lists_with_stats(buyer), 'active_pk': 'catalogo',
        'kind_nav': _kind_nav(request), 'active_kind': None,
        'fx_info': _fx_info(buyer),
        # 中文 PRIMEIRO (§5.2): o comprador é chinês, e a primeira opção de um
        # select é a que se escolhe sem pensar.
        'idiomas': sorted(settings.LANGUAGES,
                          key=lambda par: par[0] != 'zh-hans'),
    })


@partner_required
def partner_catalog_pdf(request):
    """F9 — CATÁLOGO em PDF (dono, 2026-07-10): todas as tabelas do comprador
    numa matriz compacta (o documento que ele repassa aos clientes dele).

    Parametrizado (spec v2 §5.2, 2026-08-26). Tudo tem default, e o default é
    o comportamento de julho — link guardado continua produzindo o mesmo PDF:

    ==============  ==========================================================
    ``lang``        idioma DO DOCUMENTO, independente da sessão (dono). Fora
                    de settings.LANGUAGES cai no idioma ativo.
    ``currency``    ``usd`` (default, o de julho) · ``rmb`` · ``both`` (¥ com
                    o dólar derivado embaixo). Sem taxa, cai em ``rmb``.
    ``types``       múltiplo. **Ausente = TODOS** — a tela trabalha por
                    exclusão, e tipo novo entra sozinho no catálogo.
    ``gaps``        ``show`` (default) publica a linha sem cotação em branco;
                    ``hide`` a omite.
    ``valid_until`` ``YYYY-MM-DD``. Ilegível = sem validade, nunca erro.
    ``cover_note``  recado do comprador na primeira página (400 caracteres).
    ==============  ==========================================================

    Aceita GET e POST na mesma rota (§10.2 pede POST; o card da home é GET).

    Sem cache: a tabela é viva, o PDF nasce do estado atual (é o fim da
    planilha desatualizada)."""
    from .pdf import CURRENCIES, GAPS, catalog_data, render_catalog_pdf

    # GET **e** POST: a spec v2 §10.2 manda a tela nova postar o formulário,
    # e o card da home é um GET desde julho. Ler os dois mantém o link
    # guardado funcionando — trocar por POST-só quebraria um favorito em
    # silêncio, e um catálogo é justamente o tipo de coisa que se guarda.
    dados = request.POST if request.method == 'POST' else request.GET

    lang = (dados.get('lang') or '').strip()
    if lang not in {code for code, _n in settings.LANGUAGES}:
        lang = translation.get_language() or settings.LANGUAGE_CODE
    currency = (dados.get('currency') or '').strip().lower()
    if currency not in CURRENCIES:
        currency = 'usd'
    # Sob câmbio ausente, `both` NÃO pode gerar coluna de dólar (§5.2). A tela
    # nem oferece a opção nesse estado; aqui é a rede de baixo, para o POST
    # forjado e para o link guardado de um dia em que havia taxa.
    if currency in ('both', 'usd') and _fx_info(request.buyer) is None:
        currency = 'rmb'
    gaps = (dados.get('gaps') or '').strip().lower()
    if gaps not in GAPS:
        gaps = 'show'

    # SELEÇÃO POR EXCLUSÃO (§5.2): o padrão é TUDO dentro, e tipo novo entra
    # sozinho no catálogo. Por isso a ausência do parâmetro significa "todos",
    # e não "nenhum" — que é o que uma lista de inclusões faria com um POST
    # antigo, e o comprador receberia um PDF vazio sem entender por quê.
    tipos = dados.getlist('types') if hasattr(dados, 'getlist') else []
    tipos = [k for k in tipos if k in KINDS] or None

    valid_until = _data_iso(dados.get('valid_until'))
    # Texto de capa: limite generoso, mas limite. É um recado, não um anexo —
    # e o que não couber na primeira página empurra a tabela para a segunda.
    cover_note = (dados.get('cover_note') or '').strip()[:400]

    with translation.override(lang):
        sections = catalog_data(request.buyer, currency=currency,
                                kinds=tipos, gaps=gaps)
        pdf = render_catalog_pdf(request.buyer.name, sections,
                                 currency=currency,
                                 fx=_fx_info(request.buyer),
                                 valid_until=valid_until,
                                 cover_note=cover_note)

    resp = HttpResponse(pdf, content_type='application/pdf')
    fname = f'{request.buyer.slug}-prices-{currency}-{date.today():%Y-%m-%d}.pdf'
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@partner_required
def partner_notifications(request):
    """🔔 As decisões do WhatTheChip sobre os pedidos do comprador (aprovado/
    rejeitado), mais recentes primeiro. Abrir a página marca tudo como visto
    (zera o badge). Sem nome de revisor — a decisão é 'do WhatTheChip'."""
    buyer = request.buyer
    itens = list(
        PriceChangeRequest.all_companies
        .filter(price__price_list__buyer=buyer,
                review_status__in=_DECIDIDOS)
        .select_related('price__price_list__brand')
        .order_by('-reviewed_at')[:50])
    for it in itens:
        p = it.price
        marca = (p.price_list.brand.name if p.price_list.brand_id
                 else 'Outras marcas')
        faixa = f'{p.tier_value.normalize():f}{p.tier_unit}'
        it.resumo = f'{marca} · {_KIND_LABEL.get(p.kind, p.kind)} ' \
                    f'{p.gen + " " if p.gen else ""}{faixa}'
        # F10: o pedido do parceiro é em ¥ (a moeda dele) — nunca convertido.
        # ¥ INTEIRO na exibição (dono 2026-07-27: RMB não tem casas decimais).
        if it.new_status == STATUS_QUOTED:
            it.novo = f'¥ {it.new_price.normalize():f}'
            if it.new_price_max is not None and it.new_price_max != it.new_price:
                it.novo += f'–{it.new_price_max.normalize():f}'
        else:
            it.novo = dict(STATUS_CHOICES).get(it.new_status, it.new_status)

    # As TAXAS DE CONTRATO (SSD/K9) entram na MESMA lista. Uma segunda página
    # de notificações partiria em duas uma coisa que para ele é uma só: ele
    # pediu uma mudança de preço e quer saber se passou — de que tabela ela
    # saiu é problema nosso, não dele.
    from .models import RateChangeRequest
    for it in (RateChangeRequest.all_companies
               .filter(buyer=buyer, review_status__in=_DECIDIDOS)
               .order_by('-reviewed_at')[:50]):
        it.resumo = _KIND_LABEL.get(it.kind, it.kind)
        if it.new_rate is None:
            it.novo = _('sem preço')
        elif it.kind == 'ssd':
            it.novo = _('¥ %(taxa)s/GB') % {'taxa': f'{it.new_rate.normalize():f}'}
            if it.new_floor is not None:
                it.novo += _(' · piso ¥ %(piso)s') % {
                    'piso': f'{it.new_floor.normalize():f}'}
        else:
            it.novo = _('¥ %(v)s/un.') % {'v': f'{it.new_rate.normalize():f}'}
        itens.append(it)
    # `reviewed_at` nunca é nulo aqui (só entra o já decidido), mas a ordem
    # tem de ser refeita: as duas fontes chegaram ordenadas cada uma por si.
    itens.sort(key=lambda i: i.reviewed_at, reverse=True)
    itens = itens[:50]

    _unseen_decisions(buyer).update(seen_by_partner=True)   # zera o badge
    _unseen_rates(buyer).update(seen_by_partner=True)
    return render(request, 'pricing/partner_notifications.html', {
        'buyer': buyer, 'itens': itens,
        'nav_lists': _lists_with_stats(buyer), 'active_pk': 'notifications',
        'kind_nav': _kind_nav(request), 'active_kind': None,
        'fx_info': _fx_info(buyer),
    })


@partner_required
@require_POST
def partner_kind_save(request, kind):
    """v3 (dono, 2026-07-27: "bota um botão no final pra enviar"): a página do
    tipo é UM formulário — o botão "Enviar para revisão" manda tudo e o
    servidor faz o DIFF: só linha ALTERADA vira `PriceChangeRequest` (a
    moderação segue idêntica). Semântica de célula = a da PLANILHA do
    comprador: número = ¥ cotado · "x" = não compro · vazio = sem cotação;
    faixa (só eMCP/uMCP) usa o par p<pk>/pmax<pk>. Linha not_made não
    renderiza campo e é IGNORADA aqui mesmo se vier forjada no POST."""
    if kind not in _NAV_KINDS:
        from django.http import Http404
        raise Http404
    if kind in _RATE_KINDS:
        enviados, erros = _rate_post(request, kind)
        _rate_mensagens(request, enviados, erros)
        return redirect('pricing:partner_kind', kind=kind)
    ranged = kind in ('emcp', 'umcp')
    enviados, erros = 0, []
    rows = Price.all_companies.filter(price_list__buyer=request.buyer,
                                      kind=kind)
    for p in rows:
        raw = request.POST.get(f'p{p.pk}')
        if raw is None or p.status == STATUS_NOT_MADE:
            continue                      # célula não renderizada / protegida
        raw = raw.strip().replace(',', '.')
        rotulo = (f'{_KIND_LABEL[kind]} {p.gen + " " if p.gen else ""}'
                  f'{p.tier_value.normalize():f}{p.tier_unit}')
        if raw.lower() in ('x', '×', '✗'):
            st, mn, mx = STATUS_NO_BUY, None, None
        elif raw == '':
            st, mn, mx = STATUS_UNQUOTED, None, None
        else:
            try:
                mn = mx = Decimal(raw)
                raw_max = (request.POST.get(f'pmax{p.pk}') or '') \
                    .strip().replace(',', '.')
                if ranged and raw_max:
                    mx = Decimal(raw_max)
            except InvalidOperation:
                erros.append(_('%(item)s: preço ilegível — use números ou '
                               '"x"') % {'item': rotulo})
                continue
            if mx < mn:
                erros.append(_('%(item)s: faixa invertida (máx menor que '
                               'mín)') % {'item': rotulo})
                continue
            st = STATUS_QUOTED
        # Nada mudou? Não gera pedido fantasma (mesma regra do save unitário).
        if st == p.status and (st != STATUS_QUOTED
                               or (mn, mx) == (p.price_min, p.price_max)):
            continue
        try:
            with transaction.atomic():
                PriceChangeRequest.all_companies.update_or_create(
                    price=p,
                    review_status=PriceChangeRequest.REVIEW_PENDING,
                    defaults={
                        'new_status': st, 'new_price': mn,
                        'new_price_max': (mx if mx != mn else None),
                        'old_status': p.status, 'old_price': p.price_min,
                        'requested_by': request.user,
                    })
        except (ValidationError, IntegrityError):
            erros.append(_('%(item)s: conflito ao salvar — tente de novo')
                         % {'item': rotulo})
        else:
            enviados += 1
    _rate_mensagens(request, enviados, erros)
    return redirect('pricing:partner_kind', kind=kind)


@partner_required
@require_POST
def partner_save(request, list_pk):
    """F6.1 — MODERAÇÃO: o parceiro NÃO grava o preço — grava um PEDIDO
    (`PriceChangeRequest`, pendente) que o admin aprova/rejeita no Django
    admin. Só a aprovação aplica no `Price`. Um pedido pendente por linha
    (editar de novo ATUALIZA o pedido)."""
    pl = get_object_or_404(PriceList.all_companies.filter(buyer=request.buyer),
                           pk=list_pk)

    kind = (request.POST.get('kind') or '').strip()
    gen = (request.POST.get('gen') or '').strip()
    tier_unit = (request.POST.get('tier_unit') or '').strip()
    try:
        tier_value = Decimal(request.POST.get('tier_value', ''))
    except InvalidOperation:
        tier_value = None
    # Navegação por TIPO (2026-07-27): envio vindo de /partner/tipo/<kind>/
    # volta pra lá (from_kind); sem ela, comportamento antigo (partner_list).
    from_kind = (request.POST.get('from_kind') or '').strip()

    if kind not in KINDS or tier_value is None or tier_unit not in ('GB', 'Gb'):
        messages.error(request, _('Linha inválida — recarregue a página.'))
        if from_kind in _NAV_KINDS:
            return redirect('pricing:partner_kind', kind=from_kind)
        return redirect('pricing:partner_list', list_pk=pl.pk)

    # PREÇO FIXO + ESTADO EXPLÍCITO (decisões 2026-07-07): o parceiro escolhe o
    # estado no select; "Cotado" exige o preço (um valor só — min = max interno).
    raw = (request.POST.get('price') or '').strip().replace(',', '.')
    state_req = (request.POST.get('state') or '').strip()


    def _volta():
        if from_kind in _NAV_KINDS:
            return redirect('pricing:partner_kind', kind=from_kind)
        url = redirect('pricing:partner_list', list_pk=pl.pk)
        f_kind, f_state = request.POST.get('f_kind', ''), request.POST.get('f_state', '')
        if f_kind or f_state:                      # preserva os filtros ativos
            url['Location'] += f'?kind={f_kind}&state={f_state}'
        return url

    if state_req == STATUS_QUOTED:
        if not raw:
            messages.error(request, _('Estado "Cotado" exige o preço em ¥ (RMB).'))
            return _volta()
        try:
            # F10 (RMB canônico): o ¥ digitado entra CRU no pedido — nenhuma
            # conversão aqui; o USD é derivado na leitura pelo engine.
            mn = mx = Decimal(raw)
            # Repactuação 2026-07-27: eMCP/uMCP são os ÚNICOS em FAIXA — o
            # form manda price_max separado; vazio = preço fixo (max = min).
            raw_max = (request.POST.get('price_max') or '').strip().replace(',', '.')
            if kind in ('emcp', 'umcp') and raw_max:
                mx = Decimal(raw_max)
                if mx < mn:
                    messages.error(request, _('Faixa invertida: máx menor que mín.'))
                    return _volta()
        except InvalidOperation:
            messages.error(request, _('Preço ilegível — use números (ex.: 90).'))
            return _volta()
        status, qd = STATUS_QUOTED, date.today()
    elif state_req in (STATUS_UNQUOTED, STATUS_NOT_MADE, STATUS_NO_BUY):
        status, mn, mx, qd = state_req, None, None, None
    else:
        messages.error(request, _('Estado inválido — recarregue a página.'))
        return _volta()

    obj = Price.all_companies.filter(
        price_list=pl, kind=kind, gen=gen,
        tier_value=tier_value, tier_unit=tier_unit).first()
    if obj is None:
        # Grid unificado: a linha SEMPRE existe (seed_price_grid). Sumiu =
        # página velha. Nada de criar Price por fora da moderação.
        messages.error(request, _('Linha não existe mais — recarregue a página.'))
        return _volta()

    # Nada mudou? Não gera pedido fantasma.
    if status == obj.status and (status != STATUS_QUOTED
                                 or (mn, mx) == (obj.price_min, obj.price_max)):
        messages.info(request, _('Nada a enviar — a linha já está assim.'))
        return _volta()

    try:
        with transaction.atomic():
            PriceChangeRequest.all_companies.update_or_create(
                price=obj,
                review_status=PriceChangeRequest.REVIEW_PENDING,
                defaults={
                    'new_status': status, 'new_price': mn,
                    # Faixa (2026-07-27, só eMCP/uMCP): NULL = fixo (max=min).
                    'new_price_max': (mx if mx != mn else None),
                    'old_status': obj.status, 'old_price': obj.price_min,
                    'requested_by': request.user,
                })
    except ValidationError as e:
        messages.error(request, ' · '.join(
            f'{msgs[0]}' for msgs in e.message_dict.values()))
    except IntegrityError:
        messages.error(request, _('Conflito ao salvar — tente de novo.'))
    else:
        # i18n: os rótulos exibidos traduzem; STATUS_* (chaves) nunca.
        _val = f'{mn}–{mx}' if mx != mn else f'{mn}'
        rot = {STATUS_QUOTED: _('cotado em ¥ %s') % _val,
               STATUS_NO_BUY: '"%s"' % _('não compro'),
               STATUS_UNQUOTED: _('não cotado'),
               STATUS_NOT_MADE: _('não fabricado')}
        messages.success(
            request,
            _('%(item)s → %(state)s: enviado para REVISÃO do WhatTheChip — '
              'passa a valer após a aprovação.') % {
                'item': f'{_KIND_LABEL.get(kind, kind)} '
                        f'{tier_value.normalize():f}{tier_unit}',
                'state': rot[status],
            })
    return _volta()
