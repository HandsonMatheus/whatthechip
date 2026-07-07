"""
pricing/views.py — F6: o dashboard do COMPRADOR em /partner/ (PRECIFICACAO §7.1).

É o substituto definitivo da planilha: o comprador (Wuquan) loga, vê o que falta
cotar (as "células amarelas"), o que está velho, e edita os preços DELE — em USD,
sem jamais ver auditoria (`updated_by`/`last_updated` são só do admin, §7).

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

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tenancy.scope import company_scope

from .models import (Buyer, KIND_CHOICES, KIND_UNIT, KINDS, Price, PriceList,
                     PricingConfig, STATUS_NO_BUY, STATUS_QUOTED,
                     STATUS_UNQUOTED)

#: Ordem de exibição das linhas (espelha a planilha: gerenciada → DRAM → GPU).
_KIND_ORDER = {k: i for i, (k, _) in enumerate(KIND_CHOICES)}
_KIND_LABEL = dict(KIND_CHOICES)


def partner_required(view_func):
    """Gate do parceiro: login + vínculo `Buyer.users` ativo (v1: o primeiro).

    Roda a view sob `company_scope(buyer.company)` — Camada A (contextvar) e
    Camada B (GUC do RLS) valem para a request inteira do parceiro."""
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
                return view_func(request, *args, **kwargs)
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
        d = per_list.setdefault(r['price_list_id'], {'total': 0, 'pending': 0})
        d['total'] += 1
        if r['status'] == STATUS_UNQUOTED:
            d['pending'] += 1
    for pl in lists:
        pl.stats = per_list.get(pl.pk, {'total': 0, 'pending': 0})
    # Genérica por último (a sidebar lista marcas primeiro).
    lists.sort(key=lambda pl: (pl.brand_id is None,
                               pl.brand.name if pl.brand_id else ''))
    return lists


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

    return render(request, 'pricing/partner_home.html', {
        'buyer': buyer, 'lists': lists, 'nav_lists': lists, 'active_pk': None,
        'pending': pending, 'stale': stale, 'quoted': quoted,
        'staleness_days': PricingConfig.get_config().staleness_days,
    })


def _resolution_chain_for(pl):
    """Cadeia de listas que respondem por `pl` (§4) — para exibir HERDADOS."""
    chain, seen = [], set()

    def _add(item):
        if item is not None and item.active and item.pk not in seen:
            seen.add(item.pk)
            chain.append(item)

    _add(pl)
    _add(pl.inherits_from)
    if pl.brand_id is not None:                      # a genérica cobre as de marca
        generic = (PriceList.all_companies
                   .filter(buyer=pl.buyer, brand__isnull=True, active=True)
                   .select_related('inherits_from__brand', 'brand').first())
        if generic is not None:
            _add(generic)
            _add(generic.inherits_from)
    return chain


@partner_required
def partner_list(request, list_pk):
    """Grid de edição de UMA lista — linhas próprias editáveis, herdadas
    acinzentadas (salvar numa herdada cria a linha própria = override, §4)."""
    pl = get_object_or_404(
        PriceList.all_companies.filter(buyer=request.buyer)
        .select_related('brand', 'inherits_from__brand'), pk=list_pk)

    chain = _resolution_chain_for(pl)
    merged = {}
    for source in chain:
        for p in Price.all_companies.filter(price_list=source):
            key = (p.kind, p.gen, p.tier_value, p.tier_unit)
            if key not in merged:
                p.own = (source.pk == pl.pk)
                p.source_list = source
                merged[key] = p

    rows = sorted(merged.values(),
                  key=lambda p: (_KIND_ORDER.get(p.kind, 99), p.gen, p.tier_value))
    for p in rows:
        p.kind_label = _KIND_LABEL.get(p.kind, p.kind)

    return render(request, 'pricing/partner_list.html', {
        'buyer': request.buyer, 'price_list': pl, 'rows': rows,
        'nav_lists': _lists_with_stats(request.buyer), 'active_pk': pl.pk,
    })


@partner_required
@require_POST
def partner_save(request, list_pk):
    """Salva UMA linha (própria ou override de herdada) na lista do parceiro.

    Semântica da planilha: USD preenchido → cotado (`quote_date` = hoje);
    "não compro" → NO; tudo vazio → aguardando cotação. `updated_by` gravado
    para o admin — invisível aqui."""
    pl = get_object_or_404(PriceList.all_companies.filter(buyer=request.buyer),
                           pk=list_pk)

    kind = (request.POST.get('kind') or '').strip()
    gen = (request.POST.get('gen') or '').strip()
    tier_unit = (request.POST.get('tier_unit') or '').strip()
    try:
        tier_value = Decimal(request.POST.get('tier_value', ''))
    except InvalidOperation:
        tier_value = None
    if kind not in KINDS or tier_value is None or tier_unit not in ('GB', 'Gb'):
        messages.error(request, 'Linha inválida — recarregue a página.')
        return redirect('pricing:partner_list', list_pk=pl.pk)

    no_buy = bool(request.POST.get('no_buy'))
    mn_raw = (request.POST.get('price_min') or '').strip().replace(',', '.')
    mx_raw = (request.POST.get('price_max') or '').strip().replace(',', '.')

    if no_buy:
        status, mn, mx, qd = STATUS_NO_BUY, None, None, None
    elif not mn_raw and not mx_raw:
        status, mn, mx, qd = STATUS_UNQUOTED, None, None, None
    else:
        try:
            mn = Decimal(mn_raw or mx_raw)
            mx = Decimal(mx_raw or mn_raw)
        except InvalidOperation:
            messages.error(request, 'Preço ilegível — use números (ex.: 13.50).')
            return redirect('pricing:partner_list', list_pk=pl.pk)
        status, qd = STATUS_QUOTED, date.today()

    try:
        with transaction.atomic():
            obj = Price.all_companies.filter(
                price_list=pl, kind=kind, gen=gen,
                tier_value=tier_value, tier_unit=tier_unit).first()
            if obj is None:                      # override de herdada / linha nova
                obj = Price(price_list=pl, kind=kind, gen=gen,
                            tier_value=tier_value, tier_unit=tier_unit)
            obj.status, obj.price_min, obj.price_max = status, mn, mx
            obj.quote_date = qd
            obj.updated_by = request.user        # auditoria (só o admin vê — §7)
            obj.save()
    except ValidationError as e:
        messages.error(request, ' · '.join(
            f'{msgs[0]}' for msgs in e.message_dict.values()))
    except IntegrityError:
        messages.error(request, 'Conflito ao salvar — tente de novo.')
    else:
        rot = {STATUS_QUOTED: 'cotado', STATUS_NO_BUY: 'marcado como "não compro"',
               STATUS_UNQUOTED: 'deixado como aguardando'}
        messages.success(request, f'{_KIND_LABEL.get(kind, kind)} '
                                  f'{tier_value.normalize():f}{tier_unit} {rot[status]}.')
    return redirect('pricing:partner_list', list_pk=pl.pk)
