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
    if f_kind in KINDS:
        qs = qs.filter(kind=f_kind)
    if f_state in {s for s, _ in STATUS_CHOICES}:
        qs = qs.filter(status=f_state)

    rows = sorted(qs, key=lambda p: (_KIND_ORDER.get(p.kind, 99),
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

    return render(request, 'pricing/partner_list.html', {
        'buyer': request.buyer, 'price_list': pl, 'rows': rows,
        'f_kind': f_kind, 'f_state': f_state,
        'kind_choices': KIND_CHOICES, 'state_choices': STATUS_CHOICES,
        'nav_lists': _lists_with_stats(request.buyer), 'active_pk': pl.pk,
    })


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
        it.novo = (f'US$ {it.new_price}' if it.new_status == STATUS_QUOTED
                   else dict(STATUS_CHOICES).get(it.new_status, it.new_status))

    _unseen_decisions(buyer).update(seen_by_partner=True)   # zera o badge
    return render(request, 'pricing/partner_notifications.html', {
        'buyer': buyer, 'itens': itens,
        'nav_lists': _lists_with_stats(buyer), 'active_pk': 'notifications',
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
    if kind not in KINDS or tier_value is None or tier_unit not in ('GB', 'Gb'):
        messages.error(request, 'Linha inválida — recarregue a página.')
        return redirect('pricing:partner_list', list_pk=pl.pk)

    # PREÇO FIXO + ESTADO EXPLÍCITO (decisões 2026-07-07): o parceiro escolhe o
    # estado no select; "Cotado" exige o preço (um valor só — min = max interno).
    raw = (request.POST.get('price') or '').strip().replace(',', '.')
    state_req = (request.POST.get('state') or '').strip()

    def _volta():
        url = redirect('pricing:partner_list', list_pk=pl.pk)
        f_kind, f_state = request.POST.get('f_kind', ''), request.POST.get('f_state', '')
        if f_kind or f_state:                      # preserva os filtros ativos
            url['Location'] += f'?kind={f_kind}&state={f_state}'
        return url

    if state_req == STATUS_QUOTED:
        if not raw:
            messages.error(request, 'Estado "Cotado" exige o preço em USD.')
            return _volta()
        try:
            mn = mx = Decimal(raw)
        except InvalidOperation:
            messages.error(request, 'Preço ilegível — use números (ex.: 13.50).')
            return _volta()
        status, qd = STATUS_QUOTED, date.today()
    elif state_req in (STATUS_UNQUOTED, STATUS_NOT_MADE, STATUS_NO_BUY):
        status, mn, mx, qd = state_req, None, None, None
    else:
        messages.error(request, 'Estado inválido — recarregue a página.')
        return _volta()

    obj = Price.all_companies.filter(
        price_list=pl, kind=kind, gen=gen,
        tier_value=tier_value, tier_unit=tier_unit).first()
    if obj is None:
        # Grid unificado: a linha SEMPRE existe (seed_price_grid). Sumiu =
        # página velha. Nada de criar Price por fora da moderação.
        messages.error(request, 'Linha não existe mais — recarregue a página.')
        return _volta()

    # Nada mudou? Não gera pedido fantasma.
    if status == obj.status and (status != STATUS_QUOTED or mn == obj.price_min):
        messages.info(request, 'Nada a enviar — a linha já está assim.')
        return _volta()

    try:
        with transaction.atomic():
            PriceChangeRequest.all_companies.update_or_create(
                price=obj,
                review_status=PriceChangeRequest.REVIEW_PENDING,
                defaults={
                    'new_status': status, 'new_price': mn,
                    'old_status': obj.status, 'old_price': obj.price_min,
                    'requested_by': request.user,
                })
    except ValidationError as e:
        messages.error(request, ' · '.join(
            f'{msgs[0]}' for msgs in e.message_dict.values()))
    except IntegrityError:
        messages.error(request, 'Conflito ao salvar — tente de novo.')
    else:
        rot = {STATUS_QUOTED: f'cotado em US$ {mn}',
               STATUS_NO_BUY: '"não compro"',
               STATUS_UNQUOTED: 'não cotado',
               STATUS_NOT_MADE: 'não fabricado'}
        messages.success(
            request,
            f'{_KIND_LABEL.get(kind, kind)} {tier_value.normalize():f}{tier_unit} '
            f'→ {rot[status]}: enviado para REVISÃO do WhatTheChip — passa a '
            'valer após a aprovação.')
    return _volta()
