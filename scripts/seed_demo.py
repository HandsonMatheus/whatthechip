#!/usr/bin/env python
"""
seed_demo.py — CLIENTE DE DEMONSTRAÇÃO no banco LOCAL (descartável)
====================================================================
Cria uma EMPRESA de mentira (mais um tenant, ao lado da eMiner/eRecyclo) com
usuários, lotes e vendas fictícios, para demonstrar/testar o app sem tocar em
nenhum dado real. Tudo o que ele cria pertence a essa empresa — e o ``--purge``
apaga exatamente isso e nada mais.

    python scripts/seed_demo.py                 # DRY-RUN: só diz o que faria
    python scripts/seed_demo.py --commit        # cria de verdade
    python scripts/seed_demo.py --purge --commit  # apaga a demo inteira

O que nasce (idempotente — rodar de novo não duplica):

    Empresa   Demo Recicladora (slug demo-recicladora)
    Filial    Matriz
    Usuários  demo_admin / admin · demo_gerente / gerente · demo_operador / operador
    Lotes     #1 fechado → OV confirmada → acerto → fatura → pagamento parcial
              #2 fechado → cotação viva (draft)
              #3 aberto  → em triagem (bancada)

**PNs de verdade.** As entradas saem do CATÁLOGO GLOBAL (KnownParts aprovados)
passando pelo mesmo caminho da bancada — ``classify()`` → ``_snapshot()`` →
``_price_key_fields()`` —, então a demo mostra classificação, caixa e chave de
preço reais. Só entram PNs que o comprador ativo COTA (senão a OV nasceria
impossível de confirmar).

**Comprador.** Se a empresa demo já enxerga um comprador ativo (o de
PLATAFORMA, ``company IS NULL``), usa ele e a tabela de preços real — nada é
escrito na grade dele. Se não enxerga nenhum, cria um comprador só da demo com
uma grade mínima cobrindo as categorias sorteadas.

⚠ Regra de ouro #1: quem roda é o DONO. O script recusa rodar contra qualquer
banco que não seja local (DATABASE_URL apontando pra nuvem = aborta).
⚠ Este arquivo é DESCARTÁVEL (decisão do dono, 2026-08-14): serviu, pode apagar.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model                        # noqa: E402
from django.db import transaction                                      # noqa: E402

from chips.engine import classify                                      # noqa: E402
from chips.models import KnownPart                                     # noqa: E402
from estoque.models import InventoryEntry, Lot                         # noqa: E402
from estoque.views import _price_key_fields, _snapshot                 # noqa: E402
from pricing.models import (Buyer, LotPricing, Price, PriceChangeRequest,  # noqa: E402
                            PriceList, STATUS_QUOTED, fold_gen)
from tenancy.models import Branch, Company, Membership                 # noqa: E402
from tenancy.scope import company_scope                                # noqa: E402
from vendas import services                                            # noqa: E402
from vendas.models import (DocSequence, Invoice, Payment,              # noqa: E402
                           SalesOrder, Settlement)

# ── Identidade da demo (tudo derivado daqui) ────────────────────────────────
COMPANY_NAME = 'Demo Recicladora'
COMPANY_SLUG = 'demo-recicladora'        # ⚠ 'demo' puro é slug RESERVADO (B3)
BUYER_SLUG   = 'comprador-demo'
PREFIXO      = 'demo_'                   # dono: não colidir com o admin dele
USUARIOS = [                             # (sufixo, senha, papel, nome)
    ('admin',    'admin',    Membership.ROLE_ADMIN,    'Ana (admin)'),
    ('gerente',  'gerente',  Membership.ROLE_MANAGER,  'Gil (gerente)'),
    ('operador', 'operador', Membership.ROLE_OPERATOR, 'Ope (bancada)'),
]
#: Quantos PNs distintos a demo quer, e o teto de peças examinadas. O teto é
#: alto de propósito: no banco do dono a maioria é identity-only ou está fora
#: do grid do comprador — 800 rendiam 3. Cada peça custa um classify (~ms).
ALVO_PNS       = 14
LIMITE_VARRIDO = 6000
MINIMO_PNS     = 3                       # abaixo disto a demo não se sustenta
FX_FALLBACK    = Decimal('0.1400')       # só se não houver FxRate no banco


# ═══ Guardas ════════════════════════════════════════════════════════════════

def _exige_banco_local():
    url = (os.environ.get('DATABASE_URL') or '').lower()
    if url and not any(h in url for h in ('localhost', '127.0.0.1', '/var/run')):
        sys.exit(f'ABORTADO: DATABASE_URL aponta para fora da máquina local '
                 f'({url.split("@")[-1][:40]}…). A demo é só do banco local.')


def _quantidade(pn: str) -> int:
    """Quantidade estável por PN (mesma demo em toda máquina, sem random)."""
    return 12 + (sum(ord(c) for c in pn) % 88)


# ═══ Coleta de PNs reais do catálogo ════════════════════════════════════════

def _fila_do_catalogo(buyer):
    """KnownParts na ordem que MAIS rende candidato, e só os que podem render.

    Duas lições da 1ª rodada no banco do dono (varredura alfabética achou 3
    cotáveis em 800): (a) peça **identity-only** (sem specs) nunca gera chave
    de preço — filtrar no SQL, não a golpe de classify; (b) o grid do
    comprador é POR MARCA e a lista genérica costuma ser "não cotado" → marca
    sem lista dele quase nunca fecha preço. Então: primeiro as marcas que ele
    cota, depois o resto (que ainda pode fechar pela genérica).
    """
    from django.db.models import Q
    com_specs = (Q(capacity__gt='') | Q(emcp_ram__gt='') | Q(emcp_nand__gt='')
                 | Q(density_gbit__isnull=False))
    base = (KnownPart.objects.filter(review_status='approved')
            .filter(com_specs).exclude(part_number=''))
    marcas = list(PriceList.objects.filter(buyer=buyer, active=True,
                                           brand__isnull=False)
                  .values_list('brand_id', flat=True))
    if not marcas:
        return [base.order_by('brand_id', 'part_number')]
    return [base.filter(brand_id__in=marcas).order_by('brand_id', 'part_number'),
            base.exclude(brand_id__in=marcas).order_by('brand_id', 'part_number')]


def _candidatos(buyer, origem='phone', exigir_cotado=True):
    """[(pn, snapshot, chave)] de PNs que classificam E são cotados pelo
    comprador — variedade por categoria (kind) e marca, ordem determinística.

    ``exigir_cotado=False`` quando o comprador é o da DEMO recém-criado: a
    grade dele ainda está vazia (nasce depois, das chaves daqui)."""
    from pricing.engine import BuyerPricingContext
    ctx = BuyerPricingContext(buyer)
    achados, por_kind, por_marca, vistos = [], {}, {}, set()
    lidos = sem_chave = nao_cotado = 0
    for fila in _fila_do_catalogo(buyer):
        for pn in fila.values_list('part_number', flat=True).iterator():
            if lidos >= LIMITE_VARRIDO or len(achados) >= ALVO_PNS:
                break
            if pn in vistos:
                continue
            vistos.add(pn)
            lidos += 1
            if lidos % 500 == 0:
                print(f'    … {lidos} peças examinadas, '
                      f'{len(achados)} aproveitadas')
            try:
                resultado = classify(pn)
            except Exception:
                continue
            snap = _snapshot(resultado)
            snap.pop('confidence', None)   # é de Pending/Rejected, não do Entry
            chave = _price_key_fields(resultado)
            if chave['price_tier_value'] is None:
                sem_chave += 1
                continue
            kind, marca = chave['price_kind'], snap.get('brand', '')
            if por_kind.get(kind, 0) >= 3 or por_marca.get(marca, 0) >= 3:
                continue                      # espalha categorias E marcas
            if exigir_cotado:
                cot = ctx.price_from_key(
                    kind, fold_gen(kind, chave['price_gen']),
                    chave['price_tier_value'], chave['price_tier_unit'],
                    brand_name=(resultado.get('brand') or ''), origin=origem)
                if getattr(cot, 'status', '') != 'PRICED':
                    nao_cotado += 1
                    continue                  # sem preço → OV não confirmaria
            por_kind[kind] = por_kind.get(kind, 0) + 1
            por_marca[marca] = por_marca.get(marca, 0) + 1
            achados.append((pn, snap, chave))
        if lidos >= LIMITE_VARRIDO or len(achados) >= ALVO_PNS:
            break
    print(f'  varridas {lidos} peças com specs · {sem_chave} sem chave de '
          f'preço · {nao_cotado} com chave mas fora do grid do comprador')
    return achados


# ═══ Comprador ══════════════════════════════════════════════════════════════

def _comprador(company, escrever):
    """O comprador ativo que a empresa demo enxerga; cria um só-demo se não há.
    NUNCA escreve na grade de um comprador que já existe."""
    ativos = list(Buyer.objects.filter(active=True))
    if len(ativos) == 1:
        print(f'  comprador: usando o já ativo (grade real, intocada)')
        return ativos[0], False
    if len(ativos) > 1:
        sys.exit('ABORTADO: a empresa demo enxerga 2+ compradores ativos — o '
                 'fechamento de lote exige exatamente 1. Resolva antes.')
    print('  comprador: nenhum visível → criando o da demo + grade mínima')
    if not escrever:
        return None, True
    buyer = Buyer.all_companies.create(
        company=company, name='Comprador Demo', slug=BUYER_SLUG,
        prices_in_rmb=True, fx_usd_rate=FX_FALLBACK,
        notes='Criado pelo scripts/seed_demo.py — só demonstração.')
    PriceList.all_companies.create(buyer=buyer, brand=None, company=company,
                                   notes='Grade genérica da demo.')
    return buyer, True


def _grade_minima(buyer, company, chaves):
    """Uma linha cotada por categoria sorteada (¥ determinístico pelo tier)."""
    lista = PriceList.all_companies.filter(buyer=buyer, brand=None).first()
    for kind, gen, tier, unidade in sorted(chaves):
        if Price.all_companies.filter(price_list=lista, kind=kind, gen=gen,
                                      tier_value=tier,
                                      tier_unit=unidade).exists():
            continue
        rmb = (tier * Decimal('1.5')).quantize(Decimal('0.01'))
        Price.all_companies.create(
            price_list=lista, company=company, kind=kind, gen=gen,
            tier_value=tier, tier_unit=unidade, status=STATUS_QUOTED,
            # Só o eMMC tem (e exige) origem — acordo de 2026-08-01, cravado
            # na constraint price_origin_emmc_only. Os lotes da demo são
            # 'phone', então é essa a linha que precisa existir.
            origin=('phone' if kind == 'emmc' else ''),
            price_min=rmb, price_max=rmb, source='seed_demo',
            notes='Preço fictício de demonstração.')


# ═══ Construção ═════════════════════════════════════════════════════════════

def _usuarios(company, escrever):
    """Cria/reaproveita as 3 contas da demo. Nome já ocupado por conta de FORA
    da demo = aborta (nunca sobrescreve usuário do dono)."""
    User = get_user_model()
    contas = {}
    for sufixo, senha, papel, nome in USUARIOS:
        username = f'{PREFIXO}{sufixo}'
        u = User.objects.filter(username=username).first()
        if u is not None:
            de_fora = not Membership.objects.filter(
                user=u, company=company).exists()
            if de_fora and Membership.objects.filter(user=u).exists():
                sys.exit(f'ABORTADO: o usuário {username!r} já existe e é de '
                         f'outra empresa. Troque o PREFIXO no topo do script.')
            print(f'  usuário {username}: já existe (senha inalterada)')
        else:
            print(f'  usuário {username}: criar (senha "{senha}", papel {papel})')
            if escrever:
                u = User.objects.create_user(
                    username=username, password=senha, first_name=nome,
                    is_staff=False, is_superuser=False)
        if escrever and u is not None:
            Membership.objects.update_or_create(
                user=u, company=company,
                defaults={'role': papel, 'active': True})
        contas[sufixo] = u
    return contas


def _fechar(lot, buyer):
    """Fecha o lote como a view faz: trava a taxa e gera a cotação draft."""
    from django.utils import timezone
    from pricing.engine import current_fx_rate
    taxa = current_fx_rate(buyer)[0] or FX_FALLBACK
    lot.status = Lot.STATUS_CLOSED
    lot.closed_at = timezone.now()
    lot.fx_rate = taxa
    lot.fx_source = 'seed_demo'
    lot.fx_locked_at = timezone.now()
    lot.save(update_fields=['status', 'closed_at', 'fx_rate', 'fx_source',
                            'fx_locked_at'])
    return services.create_draft_for_lot(lot, lot.operator)


def _lote(company, operador, descricao, itens, buyer, fechar=False):
    lot = Lot.open_for_company(company, operador, descricao, origin='phone')
    for pn, snap, chave in itens:
        InventoryEntry.all_companies.create(
            lot=lot, company=company, part_number=pn,
            quantity=_quantidade(pn), **snap, **chave)
    print(f'    {lot.code}: {len(itens)} PNs, '
          f'{sum(_quantidade(p) for p, _s, _c in itens)} un.')
    return (lot, _fechar(lot, buyer) if fechar else None)


def semear(escrever):
    if Company.objects.filter(slug=COMPANY_SLUG).exists():
        company = Company.objects.get(slug=COMPANY_SLUG)
        print(f'Empresa {company.name!r}: já existe (reaproveitando)')
    elif escrever:
        company = Company.objects.create(name=COMPANY_NAME, slug=COMPANY_SLUG)
        print(f'Empresa {COMPANY_NAME!r}: CRIADA')
    else:
        print(f'Empresa {COMPANY_NAME!r}: seria criada')
        company = None

    if company is None:                      # dry-run sem empresa: só o plano
        print('\n(dry-run) sem a empresa não dá para simular lotes/vendas.')
        print('Rode com --commit para criar tudo.')
        return

    with company_scope(company):
        if escrever:
            Branch.objects.get_or_create(company=company, name='Matriz')
        contas = _usuarios(company, escrever)
        buyer, novo = _comprador(company, escrever)
        if buyer is None:
            print('\n(dry-run) pararia aqui — sem comprador não há cotação.')
            return

        if SalesOrder.all_companies.filter(company=company).exists():
            print('\nJá existem vendas na demo — nada a fazer. '
                  'Use --purge --commit para começar do zero.')
            return

        print('\nProcurando PNs reais cotados pelo comprador…')
        itens = _candidatos(buyer, exigir_cotado=not novo)
        if len(itens) < MINIMO_PNS:
            sys.exit(
                f'ABORTADO: só {len(itens)} PNs cotáveis (mínimo '
                f'{MINIMO_PNS}). Sem linha cotada não há OV para demonstrar. '
                f'Confira o diagnóstico acima: "sem chave" = catálogo '
                f'identity-only; "fora do grid" = o comprador não cota essas '
                f'categorias/marcas. Nada foi criado além da empresa e dos '
                f'usuários — rode de novo depois de completar o grid.')
        print(f'  {len(itens)} PNs: '
              + ', '.join(p for p, _s, _c in itens[:6])
              + ('…' if len(itens) > 6 else ''))

        if not escrever:
            print('\n(dry-run) criaria 3 lotes com esses PNs, '
                  '2 fechados (1 com OV confirmada+fatura+pagamento) '
                  'e 1 aberto. Rode com --commit.')
            return

        if novo:
            _grade_minima(buyer, company, {
                (c['price_kind'], fold_gen(c['price_kind'], c['price_gen']),
                 c['price_tier_value'], c['price_tier_unit'])
                for _p, _s, c in itens})

        # Divisão elástica: com 14 PNs sai 7/4/3; com 3, sai 1/1/1. Os dois
        # lotes FECHADOS precisam de ≥1 item (OV sem linha não existe); o
        # aberto pode nascer vazio — a bancada da demo enche na mão.
        n = len(itens)
        c1 = max(1, n // 2)
        c2 = c1 + max(1, (n - c1) // 2) if n - c1 > 1 else c1 + (n - c1)
        lote1, lote2, lote3 = itens[:c1], itens[c1:c2], itens[c2:]

        gerente = contas['gerente']
        print('\nLotes:')
        with transaction.atomic():
            # #1 — ciclo completo: OV confirmada → acerto → fatura → pagamento
            _l1, so1 = _lote(company, gerente, 'Carga celular — jan',
                             lote1, buyer, fechar=True)
            if so1 is None:                  # create_draft_for_lot nunca levanta
                sys.exit('ABORTADO: o fechamento não gerou cotação (veja o log '
                         'do vendas). Rode --purge --commit e investigue.')
            services.confirm(so1, contas['admin'])
            linha = so1.lines.first()
            ajuste = {linha.pk: (max(1, linha.quantity // 10), None)}
            _st, inv = services.settle_and_invoice(
                so1, ajuste, contas['admin'],
                notes='Resultado do comprador (demonstração).')
            services.register_payment(
                inv, (inv.total_usd / 2).quantize(Decimal('0.01')),
                date.today() - timedelta(days=3), contas['admin'],
                reference='TT-DEMO-001')
            print(f'    → {so1.code} confirmada · {inv.code} '
                  f'com pagamento parcial')

            # #2 — cotação viva (o estado que o gerente mais vê)
            _l2, so2 = _lote(company, gerente, 'Carga celular — fev',
                             lote2, buyer, fechar=True)
            if so2 is not None:
                print(f'    → {so2.code} em cotação (draft)')

            # #3 — aberto, para a bancada ter o que triar na demo
            _lote(company, gerente, 'Lote aberto — bancada', lote3, buyer)

    print('\n✔ Demo pronta. Entre em http://127.0.0.1:8000/login/ com:')
    for sufixo, senha, papel, _n in USUARIOS:
        print(f'    {PREFIXO}{sufixo:9s} / {senha:9s}  ({papel})')


def purgar(escrever):
    company = Company.objects.filter(slug=COMPANY_SLUG).first()
    if company is None:
        print('Nada a apagar — a empresa demo não existe.')
        return
    User = get_user_model()
    with company_scope(company):
        # Ordem = a das FKs PROTECT (fatura segura acerto; acerto segura linha
        # da OV; lote segura entrada). Entrada/fila/descarte caem por CASCADE
        # do lote, mas listar explícito deixa o relatório honesto.
        alvos = {
            'pagamentos':  Payment.all_companies.filter(company=company),
            'faturas':     Invoice.all_companies.filter(company=company),
            'acertos':     Settlement.all_companies.filter(company=company),
            'ordens':      SalesOrder.all_companies.filter(company=company),
            'valorações':  LotPricing.all_companies.filter(company=company),
            'entradas':    InventoryEntry.all_companies.filter(company=company),
            'lotes':       Lot.all_companies.filter(company=company),
            'sequências':  DocSequence.all_companies.filter(company=company),
            'pedidos de preço':
                PriceChangeRequest.all_companies.filter(company=company),
            'preços':      Price.all_companies.filter(company=company),
            'listas':      PriceList.all_companies.filter(company=company),
            'compradores': Buyer.all_companies.filter(company=company),
            'vínculos':    Membership.objects.filter(company=company),
            'filiais':     Branch.objects.filter(company=company),
        }
        for nome, qs in alvos.items():
            print(f'  {nome}: {qs.count()}')
        usuarios = User.objects.filter(username__startswith=PREFIXO)
        print(f'  usuários {PREFIXO}*: {usuarios.count()}')
        if not escrever:
            print('\n(dry-run) rode com --purge --commit para apagar.')
            return
        with transaction.atomic():
            for _nome, qs in alvos.items():
                qs.delete()
            usuarios.delete()
            company.delete()
    print('✔ Demo apagada (nada fora dela foi tocado).')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Cliente de demonstração local.')
    p.add_argument('--commit', action='store_true',
                   help='Grava de verdade (sem isto: dry-run).')
    p.add_argument('--purge', action='store_true',
                   help='Apaga a empresa demo e tudo que é dela.')
    args = p.parse_args()
    _exige_banco_local()
    (purgar if args.purge else semear)(args.commit)
