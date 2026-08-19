"""
vendas/services.py — a lógica do fluxo Cotação → OV (F11.2, §12.19).

Fonte única das três operações; as views/hooks só chamam daqui:

- ``create_draft_for_lot(lot, user)`` — no FECHAMENTO do lote: agrega as
  entradas por (marca, chave de preço) e cria a cotação draft para o
  comprador ativo ÚNICO (dono, 2026-07-16: sempre Wu Quan; 0 ou 2+ ativos →
  não cria, loga — decisão humana). Nenhum preço é gravado: draft é VIVO.
- ``live_quotes(so)`` — resolve as linhas do draft contra a tabela Price
  VIVA (BuyerPricingContext — zero classify, zero query por linha).
- ``confirm(so, user)`` / ``cancel(so, user)`` — confirmação congela ¥ +
  taxa contratual + US$ linha a linha (auditoria cambial); cancelamento é
  sempre auditado (quem/quando), nunca delete.
"""

import logging

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import (DocSequence, SEQ_SO, STATUS_CANCELLED, STATUS_CONFIRMED,
                     STATUS_DRAFT, SalesOrder, SalesOrderLine)

logger = logging.getLogger(__name__)
_CENT = Decimal('0.01')


def create_draft_for_lot(lot, user=None):
    """Cotação draft do lote fechado. Devolve a SalesOrder ou None (sem
    comprador ativo único / lote sem linha com chave). NUNCA levanta — o
    fechamento do lote não pode travar por causa da venda (padrão F8)."""
    try:
        from pricing.models import Buyer
        buyers = list(Buyer.objects.filter(active=True))
        if len(buyers) != 1:
            logger.warning('vendas: lote %s fechado com %d comprador(es) '
                           'ativo(s) — cotação NÃO criada (esperado: 1).',
                           lot.pk, len(buyers))
            return None
        buyer = buyers[0]

        # Já existe cotação/OV não-cancelada? (re-fechar sem reabrir não duplica)
        if SalesOrder.all_companies.filter(lot=lot).exclude(
                status=STATUS_CANCELLED).exists():
            return None

        # Agregação por (marca, chave) — o resumo por categoria do dono; a
        # marca entra porque o comprador cota POR MARCA (grid da F6). O gen
        # DOBRA na base (fold_gen, dono 2026-07-21): LPDDR4 e LPDDR4X são a
        # MESMA categoria comercial — chaves gravadas pré-fold se fundem na
        # mesma linha aqui (em Python: o fold não é expressável no values()).
        from pricing.models import fold_gen
        raw = (lot.entries.filter(price_tier_value__isnull=False)
               .values('brand', 'price_kind', 'price_gen',
                       'price_tier_value', 'price_tier_unit')
               .annotate(qty=Sum('quantity')).order_by())
        merged = {}
        for row in raw:
            k = (row['brand'] or '', row['price_kind'],
                 fold_gen(row['price_kind'], row['price_gen']),
                 row['price_tier_value'], row['price_tier_unit'])
            merged[k] = merged.get(k, 0) + row['qty']
        unkeyed = (lot.entries.filter(price_tier_value__isnull=True)
                   .aggregate(t=Sum('quantity'))['t'] or 0)

        with transaction.atomic():
            so = SalesOrder(
                lot=lot, buyer=buyer,
                number=DocSequence.next_number(lot.company, SEQ_SO),
                unkeyed_units=unkeyed)
            so.save()
            for (brand, kind, gen, tv, tu), qty in merged.items():
                SalesOrderLine.all_companies.create(
                    order=so, brand=brand, kind=kind, gen=gen,
                    tier_value=tv, tier_unit=tu, quantity=qty)
        return so
    except Exception:
        logger.exception('vendas: falha ao criar cotação do lote %s', lot.pk)
        return None


def live_quotes(so, ctx=None):
    """[(linha, PriceQuote)] com valores VIVOS (draft) — resolve a chave da
    linha contra a tabela Price atual. Para OV confirmada, use os campos
    congelados da própria linha (unit_rmb/unit_usd).

    ``ctx`` reaproveita um ``BuyerPricingContext`` já montado. Ele custa 3
    queries e a tabela de preço é do COMPRADOR (linha de plataforma, a mesma
    para todas as empresas), então a lista de compras monta um só e passa
    para todas as ordens — senão seriam 3 queries por rascunho na tela."""
    from pricing.engine import BuyerPricingContext
    ctx = ctx or BuyerPricingContext(so.buyer)
    # Origem do LOTE da ordem (2026-08-01): decide a tabela do eMMC.
    _origin = so.lot.origin if so.lot_id else ''
    out = []
    for line in so.lines.all():
        q = ctx.price_from_key(line.kind, line.gen, line.tier_value,
                               line.tier_unit, brand_name=line.brand,
                               origin=_origin)
        out.append((line, q))
    return out


def draft_totals(pairs):
    """Totais vivos de um draft a partir de live_quotes(): (¥, US$, pendentes).
    Linha sem preço (não cotado/fora da grade/não compro) entra em pendentes."""
    total_rmb = Decimal('0.00')
    total_usd = Decimal('0.00')
    pending = []
    for line, q in pairs:
        if q.status == 'PRICED':
            # Faixa (eMCP/uMCP, repactuação 2026-07-27): draft/OV usam o
            # PONTO MÉDIO (value_rmb/value = mid; em preço fixo, é o próprio
            # valor — zero mudança para os demais). O acerto ajusta ao real.
            total_rmb += q.value_rmb() * line.quantity
            total_usd += q.value() * line.quantity
        else:
            pending.append((line, q))
    return total_rmb, total_usd, pending


def confirm(so, user, unmasked=False):
    """Draft → CONFIRMADA: congela ¥ unitário + taxa + US$ linha a linha.
    Exige TODAS as linhas cotadas (pendência = erro listando o que falta —
    força o grid do comprador a ser completado antes de vender).

    ``unmasked`` (F12): a mensagem de pendência NOMEIA categorias. Só a
    plataforma vê o rótulo real; empresa-cliente (inclusive o gerente que
    passou a confirmar — dono 2026-08-14) recebe o código C-###."""
    if so.status != STATUS_DRAFT:
        raise ValidationError('Só cotação draft pode ser confirmada.')
    pairs = live_quotes(so)
    _t_rmb, _t_usd, pending = draft_totals(pairs)
    if pending:
        annotate_labels([l for l, _q in pending], unmasked)
        faltam = '; '.join(f'{l.display_label} ({q.status})'
                           for l, q in pending[:8])
        raise ValidationError(
            f'{len(pending)} linha(s) sem preço no grid do comprador — '
            f'complete a cotação antes de confirmar: {faltam}')

    # PLANO_FX Fase C (2026-08-01): a OV HERDA a taxa TRAVADA no fechamento
    # do lote (o acordo com o comprador: mercado do dia do fechar, honrada no
    # pagamento das DUAS pontas). Lote sem trava (legado/fechado sem FxRate)
    # cai na taxa de mercado vigente na confirmação.
    from pricing.engine import current_fx_rate
    rate = (so.lot.fx_rate if so.lot_id and so.lot.fx_rate is not None
            else current_fx_rate(so.buyer)[0])
    if rate is None:
        raise ValidationError(
            'Sem taxa de câmbio: o lote não tem trava e a FxRate está '
            'vazia — rode fetch_fx_rate antes de confirmar.')
    with transaction.atomic():
        total_rmb = Decimal('0.00')
        total_usd = Decimal('0.00')
        for line, q in pairs:
            # Faixa → congela o PONTO MÉDIO (repactuação 2026-07-27); fixo →
            # o próprio valor. O acerto (F11.4) ajusta ao pago real.
            line.unit_rmb = q.value_rmb()
            line.unit_usd = (line.unit_rmb * rate).quantize(_CENT, ROUND_HALF_UP)
            line.save()
            total_rmb += line.unit_rmb * line.quantity
            # Total US$ = SOMA das linhas congeladas (estilo fatura: quem
            # confere a conta linha a linha tem que chegar no total) — NÃO
            # total_rmb × taxa, que divergiria por arredondamento por linha.
            total_usd += line.unit_usd * line.quantity
        so.fx_usd_rate = rate
        so.total_rmb = total_rmb.quantize(_CENT, ROUND_HALF_UP)
        so.total_usd = total_usd.quantize(_CENT, ROUND_HALF_UP)
        so.status = STATUS_CONFIRMED
        so.confirmed_at = timezone.now()
        so.confirmed_by = user
        so.save()
    return so


def freeze_pending_orders(buyer, user=None):
    """Congela as OVs que ficaram em RASCUNHO por falta de preço, agora que a
    tabela do comprador mudou. Devolve as que congelaram.

    POR QUE existe (dono, 2026-08-18): a OV congela no FECHAMENTO do lote
    (F11.6/F1) — o dono é categórico: "o valor já é congelado pelo próprio
    cliente no momento do fechamento". A exceção é o lote que fecha com uma
    categoria sem preço no grid do comprador: `confirm` é tudo-ou-nada, então
    a OV fica em rascunho esperando. Faltava fechar o laço — aprovar o preço
    não destravava nada, e a compra ficava presa (foi o `LOT/EMI/041`, que
    esperava LPDDR3 1.5GB).

    Chamado de onde um preço é DECIDIDO: `PriceChangeRequest.approve()` e o
    admin do `Price`. Não do `Price.save()` — importação e seed gravam
    centenas de linhas e varreriam as ordens a cada uma.

    ⚠ **Nunca levanta.** Mesmo princípio do F8: o efeito colateral não pode
    derrubar o ato principal. Aprovar preço tem que funcionar mesmo que uma
    ordem se recuse a congelar.
    """
    from tenancy.scope import company_scope
    congeladas = []
    for comp in _empresas_ativas():
        try:
            with company_scope(comp):
                # Só o que JÁ FOI DESPACHADO: aprovar preço não pode
                # atropelar o despacho e dar a venda por fechada antes de a
                # caixa sair (dono, 2026-08-18).
                pendentes = list(SalesOrder.objects.filter(
                    buyer=buyer, status=STATUS_DRAFT,
                    shipped_at__isnull=False,
                    lot__closed_at__isnull=False).select_related('lot'))
                for so in pendentes:
                    try:
                        confirm(so, user)
                        congeladas.append(so)
                    except ValidationError:
                        continue            # ainda falta preço: segue rascunho
                    except Exception:       # noqa: BLE001
                        logger.exception('freeze_pending_orders: OV %s', so.pk)
        except Exception:                   # noqa: BLE001
            logger.exception('freeze_pending_orders: empresa %s', getattr(comp, 'pk', comp))
    return congeladas


def cancel(so, user):
    """Cancela (draft OU confirmada — auditado; é o pré-requisito para
    reabrir um lote com OV confirmada). Nunca delete."""
    if so.status == STATUS_CANCELLED:
        return so
    so.status = STATUS_CANCELLED
    so.cancelled_at = timezone.now()
    so.cancelled_by = user
    so.save()
    return so


def annotate_labels(lines, unmasked: bool):
    """F12 (máscara, dono 2026-07-17): anexa ``display_label`` — plataforma
    vê o rótulo REAL ("Samsung · eMCP LPDDR4 64GB"); empresa-CLIENTE vê o
    código universal LETRA-## (convenção v3 — mesma tabela global da
    bancada/export). Leitura NUNCA cunha código (create=False): linha de
    categoria sem código (legado/kind extinto) mostra '—'."""
    if unmasked:
        for l in lines:
            l.display_label = l.label
        return lines
    from pricing.models import CategoryCode
    for l in lines:
        l.display_label = CategoryCode.label_for_key(
            l.kind, l.gen, l.tier_value, l.tier_unit, create=False) or '—'
    return lines


# ═══ Documento do GERENTE (dono, 2026-08-18) ════════════════════════════════
#
# O PDF que o gerente baixa deixou de ser "o PDF do admin com os números
# tampados de ***" e virou um documento PRÓPRIO: conferência física do que
# saiu do lote, ZERO dinheiro. Os dois resumos abaixo e o cabeçalho são a
# fonte única dele — a view só transporta, o pdf.py só desenha.
#
# ⚠ DECISÃO EXPLÍCITA DO DONO (2026-08-18) que AFROUXA a F12 neste documento:
# o resumo por tipo/capacidade mostra o rótulo REAL (eMMC 64GB) LADO A LADO
# com o código de caixa (B-07) — ou seja, entrega ao gerente o de-para das
# categorias DAQUELE lote. Foi perguntado e aprovado; não é descuido. Se um
# dia voltar atrás, o ponto de reversão é UM: ``spec_summary`` sai do
# ``manager_document`` (nada mais depende dele). O resto da máscara segue
# valendo em toda parte — bancada, tabela, export, tela da OV.


def _display_name(user) -> str:
    """Nome de quem assina — completo quando existe, senão o login."""
    if user is None:
        return ''
    return (user.get_full_name() or user.get_username()) if hasattr(
        user, 'get_username') else str(user)


def wtc_summary(lines, money=None):
    """[{label, qty, …}] por CATEGORIA WTC, marcas FUNDIDAS.

    As linhas da OV são por (marca, chave) porque o comprador cota por marca —
    então o MESMO código de caixa aparece repetido (Samsung e SanDisk eMMC
    64GB são duas linhas, ambas "B-07"). Para quem confere CAIXA isso é ruído.
    Aqui as repetições somam numa linha só. Exige ``display_label`` já anotado
    (annotate_labels).

    ``money`` = ``{line.pk: (unit_rmb, unit_usd)}`` (só na versão COM preço,
    do admin da empresa). Cada linha ganha ``unit_rmb``/``total_rmb``/
    ``total_usd``. ⚠ O **unitário só sai quando é o MESMO** em todas as
    marcas fundidas naquele código — o comprador cota por marca, então
    "B-07" pode ter dois preços; mostrar um deles seria mentira. Nesse caso o
    unitário vira ``None`` (o PDF desenha '—') e só o TOTAL, que continua
    exato, aparece. Linha sem preço também zera o unitário e conta em
    ``unpriced``.
    """
    merged = {}
    for line in lines:
        key = getattr(line, 'display_label', None) or line.label
        row = merged.setdefault(key, {'label': key, 'qty': 0, 'unit_rmb': None,
                                      'total_rmb': None, 'total_usd': None,
                                      'unpriced': 0, '_units': set()})
        row['qty'] += line.quantity
        if money is None:
            continue
        unit_rmb, unit_usd = money.get(line.pk, (None, None))
        if unit_rmb is None or unit_usd is None:
            row['unpriced'] += line.quantity
            continue
        row['_units'].add(unit_rmb)
        row['total_rmb'] = (row['total_rmb'] or Decimal('0')) + unit_rmb * line.quantity
        row['total_usd'] = (row['total_usd'] or Decimal('0')) + unit_usd * line.quantity
    for row in merged.values():
        unidades = row.pop('_units')
        if money is not None and len(unidades) == 1 and not row['unpriced']:
            row['unit_rmb'] = unidades.pop()
        for campo in ('total_rmb', 'total_usd'):
            if row[campo] is not None:
                row[campo] = row[campo].quantize(_CENT, ROUND_HALF_UP)
    # '—' (categoria sem código: kind extinto/legado) desce para o fim.
    return [v for _k, v in
            sorted(merged.items(), key=lambda kv: (kv[0] == '—', kv[0]))]


def line_money(so):
    """``{line.pk: (unit_rmb, unit_usd)}`` — VIVO no rascunho, CONGELADO na OV
    confirmada. É a mesma fonte que a tela e o PDF comercial usam; não
    reimplemente preço aqui."""
    if so.status != STATUS_DRAFT:
        return {l.pk: (l.unit_rmb, l.unit_usd) for l in so.lines.all()}
    out = {}
    for line, q in live_quotes(so):
        priced = q.status == 'PRICED'
        # Faixa (eMCP/uMCP) usa o PONTO MÉDIO, igual ao draft_totals.
        out[line.pk] = (q.value_rmb(), q.value()) if priced else (None, None)
    return out


def spec_summary(lines):
    """[{type, capacity, qty}] por TIPO × CAPACIDADE reais, marcas FUNDIDAS.

    "eMMC 64GB · 320 un." — a pergunta que o gerente faz ao conferir o lote.
    Ordem: a de ``KIND_CHOICES`` (canônica) e, dentro do tipo, capacidade
    crescente. Ver o aviso de F12 no topo desta seção.
    """
    from pricing.models import KIND_CHOICES
    ordem = {k: i for i, (k, _lbl) in enumerate(KIND_CHOICES)}
    merged = {}
    for line in lines:
        key = (line.kind, line.gen, line.tier_value, line.tier_unit)
        if key not in merged:
            merged[key] = {'type': line.type_label,
                           'capacity': line.capacity_label, 'qty': 0}
        merged[key]['qty'] += line.quantity
    return [v for _k, v in sorted(
        merged.items(),
        key=lambda kv: (ordem.get(kv[0][0], 99), kv[0][1], kv[0][2]))]


def ship_from(company) -> dict:
    """Remetente do embarque (SHIP FROM / 寄件人) — a empresa-cliente.

    O comprador recebe lote de VÁRIAS empresas (eMiner, eRecyclo…) e precisa
    saber de qual veio (dono, 2026-08-18) — por isso o nome sai SEMPRE, mesmo
    sem endereço cadastrado. O endereço vem do ``Company.address``, texto
    livre pelo mesmo motivo do SHIP TO.
    """
    if company is None:
        return {}
    return {
        'name': company.name,
        'lines': [l.strip() for l in (company.address or '').splitlines()
                  if l.strip()],
    }


def ship_to(buyer) -> dict:
    """Destinatário do embarque (SHIP TO / 收貨人) — vazio quando o comprador
    não tem endereço cadastrado.

    O PDF do lote virou também o documento que acompanha o pacote na DHL
    (dono, 2026-08-18). ``lines`` já vem quebrado por linha; o bloco NUNCA é
    inventado — comprador sem endereço simplesmente não desenha a caixa (é
    melhor a transportadora reclamar do que despachar para o lugar errado).

    ⚠ Aqui a contraparte tem NOME. Em toda superfície de empresa-cliente o
    comprador é segredo de plataforma (F11.3: o rótulo é "WhatTheChip") — a
    exceção é este bloco, e só ele: quem embarca precisa saber para onde. O
    nome do COMPRADOR continua fora; o que aparece é o DESTINATÁRIO.
    """
    if buyer is None or not (buyer.ship_to_name or buyer.ship_to_address):
        return {}
    return {
        'name': buyer.ship_to_name,
        'lines': [l.strip() for l in (buyer.ship_to_address or '').splitlines()
                  if l.strip()],
        'email': buyer.ship_to_email,
        'phone': buyer.ship_to_phone,
    }


def company_logo_bytes(company):
    """Bytes do logo da empresa-cliente (E4: blob em ``CompanyLogo``), ou
    None — para carimbar o documento de embarque com a marca de quem embarca.

    Query PRÓPRIA de propósito: a Company é lida em TODA request (middleware,
    header) e não pode arrastar um blob de até 1 MB junto. Nunca levanta —
    logo é enfeite, não pode derrubar o documento.
    """
    if company is None or not getattr(company, 'logo_mime', ''):
        return None
    try:
        from tenancy.models import CompanyLogo
        row = CompanyLogo.objects.filter(company=company).first()
        return bytes(row.data) if row and row.data else None
    except Exception:
        logger.exception('vendas: logo da empresa %s ilegível', company.pk)
        return None


#: Declaração aduaneira do embarque (dono, 2026-08-18). A transportadora EXIGE
#: descrição e valor; sem eles o pacote trava ou é reavaliado por quem não
#: conhece a carga. Texto FIXO e canônico — nunca traduz, é o que a DHL lê.
SHIPMENT_DESCRIPTION = 'PCB CHIPS FOR DISPOSAL'
SHIPMENT_VALUE_MIN, SHIPMENT_VALUE_MAX = 200, 290


def declared_value_usd(so) -> int:
    """Valor declarado do embarque, em US$ inteiros entre 200 e 290.

    ⚠ **Fictício e assumido como tal** (dono): é sucata para descarte, o valor
    aduaneiro não é o valor comercial da carga — e o comercial é justamente o
    que não pode viajar impresso na caixa.

    "Aleatório", mas **estável por documento**: sai de um hash do código da OV,
    não de `random`. Se o gerente imprimir duas vezes e sair valor diferente,
    o papel que já foi para a transportadora deixa de bater com o segundo — e
    divergência de valor declarado é exatamente o que trava um pacote na
    alfândega. Mesmo documento, mesmo número, sempre.
    """
    import hashlib
    semente = hashlib.md5((so.code or str(so.pk)).encode()).hexdigest()
    faixa = SHIPMENT_VALUE_MAX - SHIPMENT_VALUE_MIN + 1
    return SHIPMENT_VALUE_MIN + int(semente[:8], 16) % faixa


def manager_document(so, unmasked=False, with_prices=False):
    """Tudo que o PDF do gerente desenha, pronto — sem uma linha de dinheiro.

    ``unkeyed`` (chips do lote fora do grid de preço) entra nos DOIS resumos
    como linha própria: sem ele os totais não fecham com o lote físico, que é
    justamente o que este documento serve para conferir.
    """
    lines = annotate_labels(list(so.lines.all()), unmasked)
    money = line_money(so) if with_prices else None
    wtc, spec = wtc_summary(lines, money), spec_summary(lines)
    unkeyed = so.unkeyed_units or 0
    total = sum(r['qty'] for r in wtc) + unkeyed
    lot = so.lot
    return {
        'ship_from': ship_from(so.company if so.company_id else None),
        'ship_to': ship_to(so.buyer),
        'company_logo': company_logo_bytes(so.company if so.company_id else None),
        # Declaração aduaneira — exigência da transportadora. Fictícia e
        # SEMPRE preenchida: campo em branco é o que faz o pacote parar.
        'shipment_desc': SHIPMENT_DESCRIPTION,
        'shipment_value': declared_value_usd(so),
        'so_code': so.code,
        'lot_code': lot.code,
        'status': so.status,
        'company': so.company.name if so.company_id else '',
        # "Emitida em" = a data da ORDEM (congelada no documento), não a do
        # download: dois PDFs do mesmo lote têm que bater (dono, 2026-08-18).
        'issued_at': so.confirmed_at or so.created_at,
        'closed_at': lot.closed_at,
        'closed_by': _display_name(lot.closed_by_user),
        # Câmbio DO FECHAMENTO (a trava do lote — PLANO_FX Fase C). Lote
        # legado sem trava cai na taxa congelada da OV. Não é o preço de
        # nada: é taxa de mercado, pública por decisão do PLANO_FX — por isso
        # sobrevive ao gate de valor.
        'fx_rate': lot.fx_rate if lot.fx_rate is not None else so.fx_usd_rate,
        'fx_from_lot': lot.fx_rate is not None,
        'wtc': wtc,
        'spec': spec,
        'unkeyed': unkeyed,
        'total_units': total,
        # Dinheiro só existe na versão do ADMIN da empresa (dono 2026-08-18:
        # "a única diferença é que tem preços"). Sem with_prices as chaves
        # ficam None e o PDF nem desenha as colunas — a barreira continua
        # ESTRUTURAL para quem não vê valor.
        'with_prices': with_prices,
        'total_rmb': (sum((r['total_rmb'] for r in wtc
                           if r['total_rmb'] is not None), Decimal('0'))
                      if with_prices else None),
        'total_usd': (sum((r['total_usd'] for r in wtc
                           if r['total_usd'] is not None), Decimal('0'))
                      if with_prices else None),
        'unpriced_units': (sum(r['unpriced'] for r in wtc)
                           if with_prices else 0),
    }


def result_document(so, invoice):
    """Tudo que o PDF do RESULTADO desenha, pronto.

    O comprador baixa e manda pro cliente (dono, 2026-08-18) — então este
    documento é a PRESTAÇÃO DE CONTAS da compra: o que foi enviado, o que foi
    recusado, o que foi aceito e quanto disso virou dinheiro, categoria por
    categoria. É o único papel em que o cliente vê a recusa detalhada.

    Rótulo REAL, sem máscara: quem gera é o comprador, e é ele quem manda o
    documento — a máscara F12 protege o conhecimento de categoria nas telas da
    empresa-cliente, não no que o comprador escolhe compartilhar.
    """
    from pricing.models import CategoryCode
    acerto = invoice.settlement
    recusas = {sl.order_line_id: sl for sl in acerto.lines.all()}
    linhas, env, rej, ace = [], 0, 0, 0
    for line in so.lines.all().order_by('brand'):
        sl = recusas.get(line.pk)
        n_rej = sl.qty_rejected if sl else 0
        n_ace = line.quantity - n_rej
        unit = (sl.new_unit_rmb if sl and sl.new_unit_rmb is not None
                else line.unit_rmb)
        linhas.append({
            'brand': line.brand or '—',
            'type': line.type_label,
            'capacity': line.capacity_label or '—',
            'wtc': CategoryCode.label_for_key(line.kind, line.gen,
                                              line.tier_value, line.tier_unit,
                                              create=False) or '—',
            'sent': line.quantity,
            'rejected': n_rej,
            'accepted': n_ace,
            'unit_rmb': unit,
            'total_rmb': (unit * n_ace) if unit is not None else None,
        })
        env += line.quantity
        rej += n_rej
        ace += n_ace
    lot = so.lot
    return {
        'ship_from': ship_from(so.company if so.company_id else None),
        'company_logo': company_logo_bytes(so.company if so.company_id else None),
        'lot_code': lot.code,
        'so_code': so.code,
        # ⚠ Sem o código da FATURA: é papel interno do WhatTheChip e não diz
        # nada a quem recebe este documento (dono, 2026-08-18).
        'company': so.company.name if so.company_id else '',
        # ⚠ O NOME DO COMPRADOR não entra (dono, 2026-08-18): este PDF vai
        # para o cliente, e de quem o WhatTheChip compra é sigilo de negócio.
        'closed_at': lot.closed_at,
        'received_at': so.received_at,
        'settled_at': acerto.created_at,
        'notes': acerto.notes,
        # Câmbio do FECHAMENTO (PLANO_FX fase C) — a fatura usa a taxa da OV,
        # que herdou a trava do lote.
        'fx_rate': invoice.fx_usd_rate,
        'fx_locked_at': lot.fx_locked_at,
        'lines': linhas,
        'sent': env, 'rejected': rej, 'accepted': ace,
        'order_rmb': so.total_rmb, 'order_usd': so.total_usd,
        'total_rmb': invoice.total_rmb, 'total_usd': invoice.total_usd,
        # ESPERADO × FINAL, já subtraído (dono, 2026-08-18): a diferença é a
        # informação do documento — é ela que o cliente vai querer explicada.
        'delta_rmb': (invoice.total_rmb - so.total_rmb
                      if so.total_rmb is not None else None),
        'delta_usd': (invoice.total_usd - so.total_usd
                      if so.total_usd is not None else None),
    }


# ═══ F11.4 — Acerto → Fatura → Pagamentos ═══════════════════════════════════

def settle_and_invoice(so, adjustments, user, notes=''):
    """RESULTADO do comprador → Acerto + Fatura, num ato atômico (padrão
    Odoo: a OV confirmada fica INTACTA; a fatura carrega o valor final).

    ``adjustments`` = {order_line_pk: (qty_rejected, new_unit_rmb|None)} —
    linhas fora do dict ficam sem ajuste (mantêm qty e ¥ da OV). Sem NENHUM
    ajuste = fatura do valor cheio da OV (acerto vazio, registrado mesmo
    assim — auditoria de que o resultado foi "sem diferenças").

    Regras: só OV CONFIRMADA; só UMA fatura ativa por OV (re-acerto exige
    cancelar a fatura anterior — sem pagamentos); rejeitados ≤ quantidade.
    """
    from .models import (Invoice, SEQ_INVOICE, STATUS_CONFIRMED, Settlement,
                         SettlementLine)
    if so.status != STATUS_CONFIRMED:
        raise ValidationError('Acerto/fatura é de OV CONFIRMADA.')
    if Invoice.all_companies.filter(order=so).exclude(
            status='cancelled').exists():
        raise ValidationError('Esta OV já tem fatura ativa — cancele-a '
                              '(sem pagamentos) para re-acertar.')

    lines = list(so.lines.all())
    by_pk = {l.pk: l for l in lines}
    for pk, (rej, _novo) in adjustments.items():
        line = by_pk.get(pk)
        if line is None:
            raise ValidationError(f'Linha {pk} não é desta OV.')
        if rej > line.quantity:
            raise ValidationError(
                f'{line.label}: rejeitadas ({rej}) > quantidade '
                f'({line.quantity}).')

    with transaction.atomic():
        # Fechar o resultado IMPLICA que a caixa chegou: se ele não marcou o
        # recebimento antes, marca agora — senão o card de etapas mostraria
        # "Resultado" pronto com "Recebido" em aberto, que é incoerente.
        if so.received_at is None:
            so.received_at = timezone.now()
            so.save(update_fields=['received_at'])
        st = Settlement(order=so, created_by=user, notes=notes)
        st.save()
        total_rmb = Decimal('0.00')
        total_usd = Decimal('0.00')
        rate = so.fx_usd_rate
        for line in lines:
            rej, novo = adjustments.get(line.pk, (0, None))
            if rej or novo is not None:
                SettlementLine.all_companies.create(
                    settlement=st, order_line=line,
                    qty_rejected=rej, new_unit_rmb=novo)
            qty = line.quantity - rej
            unit = novo if novo is not None else line.unit_rmb
            unit_usd = (unit * rate).quantize(_CENT, ROUND_HALF_UP)
            total_rmb += unit * qty
            total_usd += unit_usd * qty          # soma por linha (F10, fatura)
        total_rmb = total_rmb.quantize(_CENT, ROUND_HALF_UP)
        total_usd = total_usd.quantize(_CENT, ROUND_HALF_UP)
        # TAXA DE SERVIÇO congelada aqui (dono, 2026-08-19), como o câmbio: é
        # a do CADASTRO no momento em que a fatura nasce. Mudar
        # `Company.service_fee_pct` depois não reescreve esta venda.
        # ⚠ O total continua CHEIO — é o que o comprador deve. A taxa só
        # muda o que o cliente recebe.
        pct = (so.company.service_fee_pct or Decimal('0.00'))
        fee_rmb = (total_rmb * pct / Decimal('100')).quantize(_CENT, ROUND_HALF_UP)
        fee_usd = (total_usd * pct / Decimal('100')).quantize(_CENT, ROUND_HALF_UP)
        inv = Invoice(
            order=so, settlement=st,
            number=DocSequence.next_number(so.company, SEQ_INVOICE),
            fx_usd_rate=rate,
            total_rmb=total_rmb,
            total_usd=total_usd,
            fee_pct=pct, fee_rmb=fee_rmb, fee_usd=fee_usd,
            issued_by=user)
        inv.save()
    return st, inv


def register_payment(invoice, amount_usd, paid_at, user, reference=''):
    """Pagamento em US$ contra a fatura; saldo zero (ou negativo? nunca —
    barra acima do saldo) marca PAGA."""
    from .models import INV_OPEN, INV_PAID, Payment
    if invoice.status != INV_OPEN:
        raise ValidationError('Só fatura EM ABERTO recebe pagamento.')
    if amount_usd <= 0:
        raise ValidationError('Valor do pagamento deve ser positivo.')
    if amount_usd > invoice.balance_usd:
        raise ValidationError(
            f'Pagamento (US$ {amount_usd}) maior que o saldo '
            f'(US$ {invoice.balance_usd}).')
    with transaction.atomic():
        p = Payment(invoice=invoice, amount_usd=amount_usd,
                    paid_at=paid_at, reference=reference, created_by=user)
        p.save()
        if invoice.balance_usd <= 0:
            invoice.status = INV_PAID
            invoice.save()
    return p


def register_payout(invoice, amount_usd, paid_at, user, reference=''):
    """REPASSE ao cliente (dono, 2026-08-19) — a perna WhatTheChip → CLIENTE.

    Espelho do ``register_payment``, do outro lado do balcão: lá é o comprador
    quitando o WTC, aqui é o WTC quitando o cliente pelo LÍQUIDO (bruto menos
    a taxa de serviço congelada na fatura).

    Trava no saldo LÍQUIDO, não no total: repassar o valor cheio seria pagar
    do próprio bolso a taxa que a plataforma acabou de cobrar.

    ⚠ Não mexe no `status` da fatura: "paga" ali quer dizer que o COMPRADOR
    quitou. As duas pernas correm em ritmos diferentes de propósito — o WTC
    pode repassar antes de receber, ou depois.
    """
    from .models import Payout
    if invoice.status == 'cancelled':
        raise ValidationError('Fatura cancelada não recebe repasse.')
    if amount_usd <= 0:
        raise ValidationError('Valor do repasse deve ser positivo.')
    if amount_usd > invoice.payout_balance_usd:
        raise ValidationError(
            f'Repasse (US$ {amount_usd}) maior que o líquido a repassar '
            f'(US$ {invoice.payout_balance_usd}).')
    return Payout.all_companies.create(
        invoice=invoice, amount_usd=amount_usd, paid_at=paid_at,
        reference=reference, created_by=user)


def payout_history(invoice):
    """Os repasses desta fatura, do mais novo ao mais velho.

    É o que a tela do CLIENTE mostra como "recebido" — dinheiro que já saiu da
    conta do WhatTheChip. O pagamento do COMPRADOR (``payment_history``) não
    entra aqui e não entra naquela tela: valor, data, referência e comprovante
    daquela perna são a conta do WTC com a contraparte, e quem é a contraparte
    é segredo de mercado (F11.3).
    """
    if invoice is None:
        return []
    return [{'pk': p.pk, 'paid_at': p.paid_at, 'amount_usd': p.amount_usd,
             'reference': p.reference}
            for p in invoice.payouts.all()]


#: Formatos aceitos no comprovante. Foto do app do banco, print da tela ou o
#: PDF do wire — é isso que existe no mundo real.
RECEIPT_MIME = {'PDF': 'application/pdf', 'PNG': 'image/png',
                'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}
RECEIPT_MAX_BYTES = 5 * 1024 * 1024        # foto de celular passa de 1 MB fácil


def _sniff_receipt(blob: bytes):
    """O formato REAL dos bytes, não a extensão do arquivo. Devolve o MIME ou
    levanta ValidationError.

    Extensão é palpite do cliente: um ``.pdf`` pode ser qualquer coisa. PDF sai
    pelo magic; imagem, pelo Pillow — que de quebra recusa SVG (não abre), e
    SVG servido inline é vetor de XSS."""
    if blob[:5] == b'%PDF-':
        return RECEIPT_MIME['PDF']
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(blob)) as img:
            fmt = img.format
    except Exception:                       # noqa: BLE001
        fmt = None
    if fmt in RECEIPT_MIME:
        return RECEIPT_MIME[fmt]
    raise ValidationError(
        'Formato não suportado no comprovante — use PDF, PNG, JPEG ou WebP.')


def attach_receipt(payment, upload):
    """Guarda o comprovante DENTRO do banco (ver PaymentReceipt).

    Levanta ValidationError em arquivo grande demais ou formato errado — quem
    chama está dentro da transação do pagamento, então recusar aqui desfaz o
    pagamento junto. É o que se quer: pagamento registrado com comprovante
    corrompido é pior do que pagamento nenhum.
    """
    from .models import PaymentReceipt
    blob = upload.read()
    if len(blob) > RECEIPT_MAX_BYTES:
        raise ValidationError(
            f'Comprovante muito grande — máximo '
            f'{RECEIPT_MAX_BYTES // (1024 * 1024)} MB.')
    if not blob:
        raise ValidationError('Comprovante vazio.')
    mime = _sniff_receipt(blob)
    return PaymentReceipt.all_companies.create(
        payment=payment, data=blob, mime=mime, size=len(blob),
        filename=(getattr(upload, 'name', '') or '')[:160])


def payment_history(invoice, com_autor=False):
    """O histórico de pagamentos da fatura, mais recente primeiro (dono,
    2026-08-18). Sempre em US$ — é a moeda em que ele paga.

    ⚠ ``com_autor`` é **False por padrão**, e o padrão é o seguro: quem
    registra o pagamento é o COMPRADOR, e o nome dele é **segredo de mercado**
    — não pode aparecer em superfície de empresa-cliente (F11.3; a contraparte
    do cliente se chama "WhatTheChip"). Vazou uma vez, em 2026-08-19, quando o
    painel de pagamento do cliente reusou este histórico com a coluna
    "Registrado por". O campo agora só existe quando quem pede é a tela DO
    COMPRADOR — omitir na origem, não esconder no template: template esconde,
    contexto vaza.
    """
    if invoice is None:
        return []
    linhas = []
    for p in invoice.payments.all().order_by('-paid_at', '-created_at'):
        recibo = getattr(p, 'receipt', None)
        linha = {
            'pk': p.pk,
            'paid_at': p.paid_at,
            'amount_usd': p.amount_usd,
            'reference': p.reference,
            'has_receipt': recibo is not None,
            'receipt_name': getattr(recibo, 'filename', '') or '',
        }
        if com_autor:
            linha['by'] = _display_name(p.created_by)
        linhas.append(linha)
    return linhas


def cancel_invoice(invoice, user):
    """Cancela fatura SEM pagamentos (pré-requisito do re-acerto)."""
    from .models import INV_CANCELLED
    if invoice.payments.exists():
        raise ValidationError('Fatura com pagamento não se cancela — '
                              'trate a diferença num novo acerto/registro.')
    invoice.status = INV_CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.save()
    return invoice


# ═══ F11.6 — a superfície do COMPRADOR (dono, 2026-08-18) ═══════════════════
#
# O comprador vê as OVs de VÁRIAS empresas. Isso é o oposto de tudo o mais no
# sistema, onde a request tem UMA empresa — e é o caso que o `partner_required`
# nunca cobriu: ele roda a view sob `company_scope(buyer.company)`, que para
# comprador de PLATAFORMA (company IS NULL, o caso do Wu Quan) é escopo NENHUM.
# Com RLS+FORCE ativos, consulta sem escopo devolve ZERO linhas em silêncio.
#
# ⚠ A saída escolhida (dono, 2026-08-18) é o LAÇO POR EMPRESA: uma consulta
# dentro do `company_scope` de cada uma. Mais lento — N consultas — mas **o
# Postgres continua sendo a barreira**: um `filter(buyer=...)` esquecido não
# vaza dado de outro cliente, porque a linha nem chega ao Python. A alternativa
# rápida (`platform_scope` + filtro no Python) desliga o filtro do banco e
# deixa a proteção inteira na mão de quem escreve a query — recusada de
# propósito. Quando N de empresas incomodar, o caminho é GUC `app.buyer_id`
# com política RLS própria, NUNCA o platform_scope.
#
# ⚠ MÁSCARA: aqui o rótulo é REAL. O comprador compra chip — o grid de preço
# dele já é por tipo e capacidade. Não use `annotate_labels(..., False)` nesta
# superfície (o `is_unmasked` é superuser-only e devolveria C-### pra ele).


def _empresas_ativas():
    from tenancy.models import Company
    return Company.objects.filter(active=True).order_by('slug')


def orders_for_buyer(buyer):
    """Todas as OVs do comprador, de TODAS as empresas, mais recentes antes.

    Cada item vem com ``stage`` (estágio comercial) já anexado. Canceladas
    ficam de fora: para o comprador elas não existem.
    """
    from tenancy.scope import company_scope
    out, ctx = [], None
    for comp in _empresas_ativas():
        with company_scope(comp):
            # ⚠ O comprador vê o que SAIU — ou o que já estava confirmado
            # (dono, 2026-08-18). A compra existe para ele quando a caixa é
            # despachada; antes disso é lote fechado na bancada do cliente, e
            # mostrar seria prometer caixa que ninguém postou.
            # ⚠⚠ O `Q(confirmada)` NÃO é enfeite: ordem anterior ao despacho
            # existir nasceu confirmada e nunca terá `shipped_at`. Sem ele, a
            # regra nova APAGA da tela toda compra antiga — foi o que
            # aconteceu em 2026-08-18 e o dono viu na hora ("todas as compras
            # do comprador sumiram"). Regra nova não pode reescrever o
            # passado.
            qs = (SalesOrder.objects
                  .filter(buyer=buyer)
                  .filter(Q(shipped_at__isnull=False)
                          | Q(status=STATUS_CONFIRMED))
                  .exclude(status=STATUS_CANCELLED)
                  .select_related('lot', 'company')
                  .prefetch_related('lines', 'invoices', 'invoices__payments'))
            for so in qs:
                # Rascunho não guarda valor nenhum: a lista mostrava "—" em
                # toda linha não congelada e o comprador não fazia ideia do
                # tamanho da compra (correção 2026-08-18, mesma do detalhe).
                # Aqui ele é re-resolvido AO VIVO contra o grid dele.
                if so.status == STATUS_DRAFT:
                    if ctx is None:
                        from pricing.engine import BuyerPricingContext
                        ctx = BuyerPricingContext(buyer)
                    rmb, usd, pendentes = draft_totals(live_quotes(so, ctx))
                    so.est_rmb, so.est_usd = rmb, usd
                    so.stage = order_stage(so, pendentes=len(pendentes))
                else:
                    so.est_rmb = so.est_usd = None
                    so.stage = order_stage(so)
                # Unidades DA ORDEM (o que ele paga). As sem chave de preço
                # viajam na caixa mas não entram no comércio — aparecem à
                # parte na tela da compra, para o total bater com o lote.
                so.units = sum(l.quantity for l in so.lines.all())
                # A fatura ATIVA (cancelada não conta): é o RESULTADO da
                # conferência — o que ele vai pagar de verdade depois de
                # recusar o que não prestava, e o saldo que falta (dono,
                # 2026-08-19). Mesma coluna existe na lista do cliente.
                so.fatura = next((i for i in so.invoices.all()
                                  if i.status != 'cancelled'), None)
                out.append(so)
    out.sort(key=lambda s: s.created_at, reverse=True)
    return out


@contextmanager
def buyer_order(buyer, pk):
    """A OV ``pk`` do comprador, JÁ dentro do escopo da empresa dona dela.

    Context manager de propósito: ler as linhas, calcular e acertar têm que
    acontecer TODOS sob o mesmo `company_scope` — fora dele o RLS devolve
    zero linhas em silêncio, e o bug apareceria como "OV sem linhas" em vez
    de erro. Levanta ``Http404`` se a OV não é deste comprador.
    """
    from django.http import Http404
    from tenancy.scope import company_scope
    for comp in _empresas_ativas():
        with company_scope(comp):
            # Mesma regra da lista (incluindo o legado confirmado): sem
            # despacho a compra não existe para ele — e 404, não 403: não
            # confirmamos nem que a ordem existe.
            so = (SalesOrder.objects
                  .filter(pk=pk, buyer=buyer)
                  .filter(Q(shipped_at__isnull=False)
                          | Q(status=STATUS_CONFIRMED))
                  .select_related('lot', 'company').first())
            if so is not None:
                yield so
                return
    raise Http404('Ordem de venda não encontrada para este comprador.')


def annotate_sales(orders):
    """Anexa a cada OV da LISTA o que a tela de vendas mostra por linha.

    Uma volta só para as três perguntas que o dono quer responder de relance
    (2026-08-19): *quantos chips saíram*, *quanto se esperava* e *quanto ainda
    tem a receber* — antes a lista só tinha código, status e data, e ele
    precisava abrir ordem por ordem para saber o tamanho de cada uma.

    Campos anexados (nas INSTÂNCIAS, nunca no banco):

    · ``units``       — chips DA ORDEM (o que vira dinheiro; as sem chave de
      preço viajam na caixa e aparecem à parte no detalhe);
    · ``est_rmb``/``est_usd`` — rascunho não guarda valor: o esperado é
      re-resolvido AO VIVO contra o grid do comprador (mesma conta da lista
      dele). Confirmada já tem ``total_rmb``/``total_usd`` congelados;
    · ``fatura``      — a fatura ATIVA (cancelada não conta), ou ``None``;
    · ``receber_usd`` + ``receber_est`` — o que falta entrar. Com fatura é o
      SALDO (final − pago); sem fatura ainda é o esperado, e aí ``receber_est``
      marca que aquilo é estimativa, não promessa.

    ⚠ Cotação viva é cara: o ``BuyerPricingContext`` é reaproveitado por
    comprador (a lista costuma ter um só).
    """
    ctxs = {}
    for so in orders:
        so.units = sum(l.quantity for l in so.lines.all())
        so.est_rmb = so.est_usd = None
        if so.status == STATUS_DRAFT:
            ctx = ctxs.get(so.buyer_id)
            if ctx is None:
                from pricing.engine import BuyerPricingContext
                ctx = ctxs[so.buyer_id] = BuyerPricingContext(so.buyer)
            so.est_rmb, so.est_usd, _pend = draft_totals(live_quotes(so, ctx))
        so.fatura = next((i for i in so.invoices.all()
                          if i.status != 'cancelled'), None)
        if so.status == STATUS_CANCELLED:
            # Ordem cancelada não tem o que receber — e "US$ 0,00" numa linha
            # apagada se lê como dívida quitada, que é outra coisa.
            so.receber_usd, so.receber_est = None, False
        elif so.fatura is not None:
            so.receber_usd, so.receber_est = so.fatura.balance_usd, False
        else:
            so.receber_usd = (so.total_usd if so.total_usd is not None
                              else so.est_usd)
            so.receber_est = so.receber_usd is not None
    return orders


#: Estágios comerciais que o comprador vê. Canônicos (a chave nunca traduz);
#: o rótulo é montado na view/template.
STAGE_SEM_PRECO, STAGE_A_CONGELAR = 'sem_preco', 'a_congelar'
STAGE_A_CONFERIR = 'a_conferir'
STAGE_FATURADO, STAGE_PARCIAL, STAGE_PAGO = 'faturado', 'parcial', 'pago'


def order_stage(so, pendentes=None) -> str:
    """Em que pé está a compra, do ponto de vista do COMPRADOR.

    Os dois estágios de RASCUNHO são coisas diferentes, e confundi-los foi um
    bug real (dono, 2026-08-18): ele aprovou o preço que faltava e a lista
    continuou dizendo "falta preço seu", travada.

    · ``sem_preco``  — alguma categoria não tem preço no grid DELE. É a única
      pendência que o comprador resolve sozinho: completando a tabela.
    · ``a_congelar`` — todas cotadas, falta só CONGELAR (quem congela é ele,
      decisão do dono 2026-08-18; até então a tela mandava "falar com o
      WhatTheChip" e não havia caminho nenhum).

    ``pendentes`` evita recalcular as cotações vivas quem já as tem em mão.
    """
    if so.status == STATUS_DRAFT:
        if pendentes is None:
            pendentes = len(draft_totals(live_quotes(so))[2])
        return STAGE_SEM_PRECO if pendentes else STAGE_A_CONGELAR
    inv = next((i for i in so.invoices.all() if i.status != 'cancelled'), None)
    if inv is None:
        return STAGE_A_CONFERIR              # confirmada, resultado pendente
    if inv.status == 'paid':
        return STAGE_PAGO
    return STAGE_PARCIAL if inv.paid_usd else STAGE_FATURADO


def result_rows(so):
    """``[{'brand': str, 'lines': [...], 'qty', 'rmb'}]`` — o que a tela do
    resultado desenha.

    **Agrupa por MARCA, e dentro dela por capacidade** (dono, 2026-08-18).
    Fundir por capacidade deixaria a tela mais bonita mas cria dedução
    AMBÍGUA em lote PCB, onde o preço é POR MARCA: "recusei 10 de eMMC 64GB"
    não diria de qual marca sai o desconto. Assim cada linha da tela é uma
    linha da OV — o abatimento é sempre exato.

    **Rascunho mostra valor AO VIVO** (correção 2026-08-18, achada em prod no
    lote 042): a OV congelada guarda o ¥ na linha, mas o rascunho não guarda
    NADA — a tela saía com uma parede de "—" e o comprador não tinha como
    saber o que faltava. Agora o rascunho re-resolve contra o grid dele na
    leitura (mesma fonte que a tela do admin usa) e marca linha a linha o que
    está **sem preço**. Valor de rascunho é ESTIMATIVA: quem manda é o
    congelado, e a tela precisa dizer isso.
    """
    from pricing.models import CategoryCode
    # Rascunho: ¥ E US$ vivos. O US$ importa porque a tela do CLIENTE é em
    # dólar — sem ele o admin via "—" na ordem ainda não despachada.
    vivo, vivo_usd = {}, {}
    if so.status == STATUS_DRAFT:
        for line, q in live_quotes(so):
            priced = q.status == 'PRICED'
            vivo[line.pk] = q.value_rmb() if priced else None
            vivo_usd[line.pk] = q.value() if priced else None
    # RESULTADO por linha, quando já houve acerto (dono, 2026-08-18: a tela do
    # CLIENTE tem que ser a mesma tabela — "é o mais importante do vendedor
    # saber"). Sem acerto, recusados = 0 e aprovados = enviados.
    recusas = {}
    inv = next((i for i in so.invoices.all() if i.status != 'cancelled'), None)
    if inv is not None and inv.settlement_id:
        recusas = {sl.order_line_id: sl for sl in inv.settlement.lines.all()}
    grupos = {}
    for line in so.lines.all():
        g = grupos.setdefault(line.brand or '—',
                              {'brand': line.brand or '—', 'lines': [],
                               'qty': 0, 'rmb': Decimal('0.00'),
                               'sem_preco': 0, 'rejected': 0, 'accepted': 0})
        if so.status == STATUS_DRAFT:
            unit, unit_usd, estimado = (vivo.get(line.pk),
                                        vivo_usd.get(line.pk), True)
        else:
            unit, unit_usd, estimado = line.unit_rmb, line.unit_usd, False
        total = (unit * line.quantity) if unit is not None else None
        sl = recusas.get(line.pk)
        rej = sl.qty_rejected if sl else 0
        ace = line.quantity - rej
        g['lines'].append({
            'pk': line.pk,
            'type': line.type_label,
            'capacity': line.capacity_label or '—',
            # Código de caixa: o vocabulário que ele e a bancada compartilham.
            'wtc': CategoryCode.label_for_key(line.kind, line.gen,
                                              line.tier_value, line.tier_unit,
                                              create=False) or '—',
            'qty': line.quantity,
            'rejected': rej,
            'accepted': ace,
            'unit_rmb': unit,
            'unit_usd': unit_usd,
            'total_rmb': total,
            'total_usd': ((unit_usd * line.quantity)
                          if unit_usd is not None else None),
            # ¥/US$ do que foi ACEITO — é o que virou dinheiro de verdade.
            'pago_rmb': (unit * ace) if unit is not None else None,
            'pago_usd': (unit_usd * ace) if unit_usd is not None else None,
            'estimado': estimado,
            'sem_preco': unit is None,
            'tem_resultado': inv is not None,
        })
        g['qty'] += line.quantity
        g['rejected'] += rej
        g['accepted'] += ace
        if total is not None:
            g['rmb'] += total
        else:
            g['sem_preco'] += line.quantity
    for g in grupos.values():
        g['lines'].sort(key=lambda r: (r['type'], r['capacity']))
    return sorted(grupos.values(), key=lambda g: g['brand'])


def _entry_spec(e) -> str:
    """A spec que o comprador confere no PN: capacidade, ou NAND+RAM no
    combo (é assim que eMCP/uMCP são anunciados e conferidos)."""
    if e.is_emcp and (e.emcp_nand or e.emcp_ram):
        return ' + '.join(p for p in (e.emcp_nand, e.emcp_ram) if p)
    return e.capacity or '—'


def lot_chips(so):
    """TODO chip do lote, PN a PN — a aba de detalhe do comprador (dono,
    2026-08-18: "seria aí onde o comprador olha detalhe por detalhe").

    Cada linha traz PN, marca, tipo, spec, quantidade, a CAIXA WTC em que ele
    foi despachado e o preço da categoria. O preço vem da OV (congelado) ou do
    grid vivo (rascunho) — a MESMA fonte da tabela de cima, casando pela chave
    de preço (marca × kind/gen/faixa). PN sem chave de preço aparece com "—":
    ele viaja na caixa mas não entra no comércio, e o comprador precisa ver
    isso em vez de achar que sumiu.

    ⚠ Roda DENTRO do `company_scope` da dona (o `buyer_order` abre) — o lote é
    da empresa-cliente e o RLS devolveria zero linhas fora dele.
    """
    from estoque.models import InventoryEntry
    from pricing.models import CategoryCode
    vivo = {}
    if so.status == STATUS_DRAFT:
        for line, q in live_quotes(so):
            vivo[line.pk] = q.value_rmb() if q.status == 'PRICED' else None
    precos = {}
    for line in so.lines.all():
        unit = vivo.get(line.pk) if so.status == STATUS_DRAFT else line.unit_rmb
        precos[(line.brand or '', line.kind, line.gen,
                line.tier_value, line.tier_unit)] = unit

    linhas, total_qty, total_rmb = [], 0, Decimal('0.00')
    for e in (InventoryEntry.objects.filter(lot=so.lot)
              .order_by('brand', 'part_number')):
        chave = (e.brand or '', e.price_kind, e.price_gen,
                 e.price_tier_value, e.price_tier_unit)
        unit = precos.get(chave)
        total = (unit * e.quantity) if unit is not None else None
        linhas.append({
            'pn': e.part_number,
            'brand': e.brand or '—',
            'type': e.chip_type or '—',
            'spec': _entry_spec(e),
            'qty': e.quantity,
            'wtc': (CategoryCode.label_for_key(
                e.price_kind, e.price_gen, e.price_tier_value,
                e.price_tier_unit, create=False) or '—') if e.price_kind else '—',
            'unit_rmb': unit,
            'total_rmb': total,
        })
        total_qty += e.quantity
        if total is not None:
            total_rmb += total
    return {'linhas': linhas, 'qty': total_qty, 'rmb': total_rmb}


#: Etapas da compra, na ordem em que acontecem. Chaves CANÔNICAS (nunca
#: traduzem); o rótulo é montado no template.
STEP_FECHADO, STEP_ENVIADO, STEP_RECEBIDO = 'fechado', 'enviado', 'recebido'
STEP_RESULTADO, STEP_PAGAMENTO = 'resultado', 'pagamento'


def order_steps(so):
    """O card de etapas: por onde a compra passou, onde está, para onde vai.

    Cinco etapas, cada uma com data REAL. "Enviado" entrou com a F4 (o cliente
    registra transportadora, rastreio e data).

    Cada item: ``{key, date, state}``:

      · ``done``    — tem data;
      · ``current`` — a primeira SEM data que ainda não foi ultrapassada: é o
        que falta fazer AGORA;
      · ``pulado``  — sem data, mas uma etapa POSTERIOR já aconteceu. É o
        cliente que esqueceu de registrar o envio e a caixa chegou assim
        mesmo — nada bloqueia isso, e a tela não pode mentir dizendo que a
        compra está "aguardando envio" com o resultado já fechado;
      · ``todo``    — ainda vem pela frente.
    """
    inv = next((i for i in so.invoices.all() if i.status != 'cancelled'), None)
    pago = inv.balance_usd <= 0 if inv is not None else False
    passos = [
        {'key': STEP_FECHADO,   'date': so.lot.closed_at if so.lot_id else None},
        {'key': STEP_ENVIADO,   'date': so.shipped_at},
        {'key': STEP_RECEBIDO,  'date': so.received_at},
        {'key': STEP_RESULTADO, 'date': inv.settlement.created_at if inv else None},
        {'key': STEP_PAGAMENTO, 'date': (inv.payments.order_by('-paid_at')
                                         .values_list('paid_at', flat=True)
                                         .first() if pago else None)},
    ]
    ultimo_com_data = max((i for i, p in enumerate(passos)
                           if p['date'] is not None), default=-1)
    corrente = True
    for i, p in enumerate(passos):
        if p['date'] is not None:
            p['state'] = 'done'
        elif i < ultimo_com_data:
            p['state'] = 'pulado'
        elif corrente:
            p['state'] = 'current'
            corrente = False
        else:
            p['state'] = 'todo'
    return passos


#: Rastreio clicável por transportadora. Chave = o que o cliente digita,
#: normalizado (minúsculas, sem espaço). Transportadora desconhecida cai no
#: texto puro — melhor sem link do que com link quebrado.
TRACKING_URL = {
    'dhl': 'https://www.dhl.com/global-en/home/tracking.html?tracking-id={}',
    'fedex': 'https://www.fedex.com/fedextrack/?trknbr={}',
    'ups': 'https://www.ups.com/track?tracknum={}',
}


def tracking_url(carrier, tracking):
    """URL de rastreio, ou None. Nunca levanta — link é conveniência."""
    if not carrier or not tracking:
        return None
    chave = ''.join(c for c in carrier.lower() if c.isalnum())
    modelo = TRACKING_URL.get(chave)
    return modelo.format(tracking.strip()) if modelo else None


def mark_shipped(so, carrier, tracking, quando, user):
    """Registra (ou CORRIGE) o despacho do lote — F4, dono 2026-08-18.

    Quem embarca é o CLIENTE: transportadora, rastreio e data saem da mão de
    quem leva a caixa. Uma caixa por lote (decisão do dono) — daí os campos
    morarem na própria OV.

    ⚠ **Editável de propósito**, ao contrário do `received_at`: número de
    rastreio digitado errado tem que ser corrigível, e às vezes ele só aparece
    horas depois do despacho. O pghistory guarda cada correção.

    Data é obrigatória (é ela que a etapa mostra); rastreio pode entrar depois.
    """
    quando = quando or timezone.localdate()
    if not (carrier or '').strip():
        raise ValidationError('Informe a transportadora.')
    if quando > timezone.localdate():
        raise ValidationError('A data do despacho não pode ser no futuro.')
    novo_despacho = so.shipped_at is None
    so.carrier = (carrier or '').strip()[:40]
    so.tracking = (tracking or '').strip()[:60]
    so.shipped_at = quando
    so.shipped_by = user
    so.save(update_fields=['carrier', 'tracking', 'shipped_at', 'shipped_by'])
    # ── O DESPACHO é que CONGELA a venda (dono, 2026-08-18) ────────────────
    # Fechar o lote é ato de bancada; a venda só existe de verdade quando a
    # caixa SAI. Daqui em diante o ¥ para de andar e a ordem aparece para o
    # comprador.
    # ⚠ Padrão F8: NUNCA levanta. Categoria sem preço no grid do comprador não
    # pode impedir de registrar que a caixa saiu — o fato físico aconteceu. A
    # ordem fica em rascunho DESPACHADO, aparece para o comprador assim mesmo
    # (é ele quem completa a tabela) e congela quando o preço entrar.
    if novo_despacho and so.status == STATUS_DRAFT:
        try:
            confirm(so, user)
        except ValidationError:
            logger.info('mark_shipped: OV %s despachada sem congelar (falta '
                        'preço no grid do comprador)', so.pk)
        except Exception:                        # noqa: BLE001
            logger.exception('mark_shipped: falha ao congelar a OV %s', so.pk)
    return so


def mark_received(so, quando=None):
    """Marca a chegada da caixa. Idempotente: a primeira data vale — remarcar
    reescreveria um fato do passado."""
    if so.received_at is not None:
        return so
    so.received_at = quando or timezone.now()
    so.save(update_fields=['received_at'])
    return so


def category_glossary(so=None):
    """O dicionário da convenção WTC: ``A-01`` = o quê, exatamente.

    Existe porque o comprador recebe as caixas rotuladas com o código e
    precisa ir se adaptando à convenção (dono, 2026-08-18). Mostra a tabela
    INTEIRA — é uma convenção universal, não uma lista deste lote — e marca as
    categorias que vieram NESTA compra, que são por onde ele começa a ler.

    ⚠ Ordem por LETRA e número, a mesma da caixa física. Nunca por preço nem
    por capacidade: a escadinha de capacidade é justamente o que a máscara F12
    esconde (`pricing/convention.py`).
    """
    from pricing.models import CategoryCode
    from pricing.convention import KIND_LETTER
    no_lote = set()
    if so is not None:
        for line in so.lines.all():
            rotulo = CategoryCode.label_for_key(line.kind, line.gen,
                                                line.tier_value, line.tier_unit,
                                                create=False)
            if rotulo:
                no_lote.add(rotulo)
    linhas = []
    for c in CategoryCode.objects.all():
        nesta = c.label in no_lote
        # Categoria APOSENTADA sai da lista — ela não faz mais parte da
        # convenção viva. Exceção: se veio NESTA compra, entra; a caixa com o
        # rótulo antigo está fisicamente na mão dele, e ele precisa saber o
        # que aquele código significa.
        if getattr(c, 'retired_at', None) is not None and not nesta:
            continue
        linhas.append({
            'code': c.label,
            'letter': KIND_LETTER.get(c.kind, '?'),
            'type': c.gen or dict(_KIND_LABEL()).get(c.kind, c.kind),
            'capacity': (f'{c.tier_value.normalize():f}{c.tier_unit}'
                         if c.tier_unit else '—'),
            'no_lote': nesta,
            'retired': getattr(c, 'retired_at', None) is not None,
        })
    return sorted(linhas, key=lambda l: (l['letter'], l['code']))


def _KIND_LABEL():
    from pricing.models import KIND_CHOICES
    return KIND_CHOICES


def draft_pendencias(grupos):
    """As categorias do rascunho que não têm preço no grid do comprador —
    o que ele precisa cotar para a ordem congelar. Lista curta e nomeada:
    "faltam N categorias" sem dizer QUAIS não ajuda ninguém."""
    return [f"{l['type']} {l['capacity']}".strip()
            for g in grupos for l in g['lines'] if l['sem_preco']]
