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
from django.views.decorators.http import require_POST

from tenancy.scope import company_scope

from .models import (Buyer, KIND_CHOICES, KIND_UNIT, KINDS, Price,
                     PriceChangeRequest, PriceList, PricingConfig,
                     STATUS_CHOICES, STATUS_NO_BUY, STATUS_NOT_MADE,
                     STATUS_QUOTED, STATUS_UNQUOTED)

#: Ordem de exibição das linhas (espelha a planilha: gerenciada → DRAM → GPU).
_KIND_ORDER = {k: i for i, (k, _) in enumerate(KIND_CHOICES)}
_KIND_LABEL = dict(KIND_CHOICES)


def _unseen_decisions(buyer):
    """🔔 Decisões (aprovado/rejeitado) que o parceiro ainda não viu."""
    return PriceChangeRequest.all_companies.filter(
        price__price_list__buyer=buyer,
        review_status__in=(PriceChangeRequest.REVIEW_APPROVED,
                           PriceChangeRequest.REVIEW_REJECTED),
        seen_by_partner=False)


def partner_required(view_func):
    """Gate do parceiro: login + vínculo `Buyer.users` ativo (v1: o primeiro).

    Roda a view sob `company_scope(buyer.company)` — Camada A (contextvar) e
    Camada B (GUC do RLS) valem para a request inteira do parceiro. Também
    anexa `request.partner_unseen` (badge 🔔 em toda página do parceiro)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        buyer = (Buyer.all_companies.filter(users=request.user, active=True)
                 .select_related('company').first())
        if buyer is None:
            raise PermissionDenied(
                'Esta área é do comprador. Sua conta não está vinculada a '
                'nenhum comprador ativo.')
        request.buyer = buyer
        if buyer.company_id:
            with company_scope(buyer.company):
                request.partner_unseen = _unseen_decisions(buyer).count()
                return view_func(request, *args, **kwargs)
        request.partner_unseen = _unseen_decisions(buyer).count()
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
# Só DDR/eMMC/UFS são por marca (matriz); eMCP/uMCP/LPDDR são unificados
# (coluna única, linha na genérica). SSD é linear ¥/GB (sem grid) — fora.
_NAV_KINDS = ('emcp', 'umcp', 'lpddr', 'emmc', 'ufs', 'ddr')
_MATRIX_KINDS = ('emmc', 'ufs', 'ddr')


def _kind_nav(buyer):
    """[(kind, label, pendentes)] p/ a sidebar — badge = não-cotados do tipo."""
    from django.db.models import Count
    pend = {d['kind']: d['n']
            for d in Price.all_companies
            .filter(price_list__buyer=buyer, status=STATUS_UNQUOTED)
            .values('kind').annotate(n=Count('id'))}
    return [(k, _KIND_LABEL[k], pend.get(k, 0)) for k in _NAV_KINDS]


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

    ctx = {'buyer': request.buyer, 'kind': kind,
           'kind_label': _KIND_LABEL[kind],
           'unified': kind in UNIFIED_KINDS,
           'ranged': kind in ('emcp', 'umcp'),
           'kind_nav': _kind_nav(request.buyer), 'active_kind': kind,
           'active_pk': None}

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

    if kind in UNIFIED_KINDS:
        rows = sorted(Price.all_companies.filter(price_list=generica,
                                                 kind=kind),
                      key=lambda p: (p.gen, p.tier_value))
        for p in rows:
            p.pending = pendentes.get(p.pk)
            p.pend_disp = _pend_disp(p.pending)
            p.tier_disp = _fmt(p.tier_value)
            p.min_disp, p.max_disp = _fmt(p.price_min), _fmt(p.price_max)
        ctx.update({'rows': rows, 'generica': generica})
        return render(request, 'pricing/partner_kind.html', ctx)

    # matriz: colunas = marcas com linha deste tipo (+ Outras/genérica)
    all_rows = list(Price.all_companies.filter(price_list__buyer=request.buyer,
                                               kind=kind)
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
                p.min_disp = _fmt(p.price_min)
            cells.append((pl, p))
        linhas.append({'gen': gen, 'tier': _fmt(tier), 'unit': unit,
                       'cells': cells})
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
    kinds_resumo = [
        {'kind': k, 'label': lbl,
         'quoted': por_kind.get(k, {}).get(STATUS_QUOTED, 0),
         'pending': pend}
        for k, lbl, pend in _kind_nav(buyer)]
    return render(request, 'pricing/partner_home.html', {
        'buyer': buyer, 'lists': lists, 'nav_lists': lists, 'active_pk': None,
        'kind_nav': _kind_nav(buyer), 'active_kind': None,
        'kinds_resumo': kinds_resumo,
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
        'kind_nav': _kind_nav(request.buyer), 'active_kind': None,
    })


@partner_required
def partner_how(request):
    """'Como funciona' — guia CURTO do dashboard para o comprador (pedido do
    dono, 2026-07-09: comunicação objetiva, o comprador chinês não gosta de
    ler). Conteúdo 100% no template, marcado com {% trans %} (MULTILANGUAGE §7)."""
    return render(request, 'pricing/partner_how.html', {
        'buyer': request.buyer,
        'nav_lists': _lists_with_stats(request.buyer), 'active_pk': 'how',
        'kind_nav': _kind_nav(request.buyer), 'active_kind': None,
    })


@partner_required
def partner_catalog_pdf(request):
    """F9 — CATÁLOGO em PDF (dono, 2026-07-10): todas as tabelas do comprador
    numa matriz compacta (o documento que ele repassa aos clientes dele).

    ``?lang=`` escolhe o idioma DO DOCUMENTO (seletor próprio na home —
    decisão do dono: independe do idioma da sessão). Valor fora de
    settings.LANGUAGES cai no idioma ativo da sessão. ``?currency=rmb|usd``
    (F10.6) escolhe a MOEDA do documento: usd = derivado pela taxa contratual
    (default — é o que circula pros clientes dele hoje); rmb = o ¥ armazenado.
    Sem cache: a tabela é viva, o PDF nasce do estado atual (é o fim da
    planilha desatualizada)."""
    from .pdf import catalog_data, render_catalog_pdf   # reportlab só aqui

    lang = (request.GET.get('lang') or '').strip()
    if lang not in {code for code, _n in settings.LANGUAGES}:
        lang = translation.get_language() or settings.LANGUAGE_CODE
    currency = (request.GET.get('currency') or '').strip().lower()
    if currency not in ('rmb', 'usd'):
        currency = 'usd'
    with translation.override(lang):
        columns, sections = catalog_data(request.buyer, currency=currency)
        pdf = render_catalog_pdf(request.buyer.name, columns, sections,
                                 currency=currency)

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
                review_status__in=(PriceChangeRequest.REVIEW_APPROVED,
                                   PriceChangeRequest.REVIEW_REJECTED))
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

    _unseen_decisions(buyer).update(seen_by_partner=True)   # zera o badge
    return render(request, 'pricing/partner_notifications.html', {
        'buyer': buyer, 'itens': itens,
        'nav_lists': _lists_with_stats(buyer), 'active_pk': 'notifications',
        'kind_nav': _kind_nav(buyer), 'active_kind': None,
    })


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
