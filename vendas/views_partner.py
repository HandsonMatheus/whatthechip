"""
vendas/views_partner.py — a superfície do COMPRADOR (F11.6, dono 2026-08-18)
============================================================================
O acerto do F11.4 trocando de mão: quem dá o RESULTADO deixa de ser o admin da
plataforma e passa a ser o COMPRADOR, na área dele (``/partner/compras/``).
Modelo é o mesmo — ``Settlement``/``SettlementLine``/``Invoice`` +
``settle_and_invoice`` — o que muda é a superfície.

Duas telas:

1. **Compras** — as OVs de TODOS os clientes dele (lote, cliente, chips,
   ¥/US$, estágio). O laço por empresa mora no ``services.orders_for_buyer``.
2. **Compra** — a OV aberta: cabeçalho, tabela MARCA → capacidade com o campo
   de RECUSADOS por linha, observação, e o "Fechar resultado" que gera acerto
   + fatura num ato atômico. Depois de faturada, a mesma tela vira leitura,
   com o saldo a pagar.

⚠ Três coisas que esta superfície faz DIFERENTE do resto do sistema, e que a
próxima pessoa precisa saber antes de editar:

· **Escopo:** o comprador lê VÁRIAS empresas. Toda leitura/escrita passa pelo
  ``services.buyer_order``/``orders_for_buyer``, que abrem o ``company_scope``
  da empresa dona. Fora dele o RLS devolve ZERO linhas em silêncio — o bug
  apareceria como "OV sem linhas", não como erro.
· **Máscara:** aqui o rótulo é REAL (``eMMC 64GB``, não ``B-07``). O
  ``is_unmasked`` é superuser-only e o comprador não é superuser; usar os
  helpers mascarados aqui entregaria código de caixa a quem compra chip.
· **Posse:** o gate é o ``partner_required`` (vínculo ``Buyer.users``), e TODA
  query filtra por ``buyer=request.buyer``. Uma OV de outro comprador é 404,
  não 403 — não confirmamos nem que ela existe.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from pricing.views import _fx_info, partner_required

from . import services
from .models import STATUS_CONFIRMED, Payment, Wallet


def _shell(request, extra=None):
    """Contexto que o ``partner_base.html`` exige (header + sidebar)."""
    ctx = {'buyer': request.buyer, 'fx_info': _fx_info(request.buyer),
           'active_pk': 'compras', 'active_kind': None, 'kind_nav': []}
    ctx.update(extra or {})
    return ctx


def _stage_labels():
    """Rótulo humano de cada estágio. Função, não constante: o `gettext` tem
    de rodar POR REQUEST, no idioma ativo — resolvido no import, todo mundo
    leria o primeiro idioma que carregou o módulo.

    ⚠ As CHAVES (`sem_preco`, `a_conferir`…) são canônicas e nunca traduzem.
    """
    return {
        services.STAGE_SEM_PRECO:  _('Falta preço seu'),
        services.STAGE_A_CONGELAR: _('Congelar'),
        services.STAGE_A_CONFERIR: _('Em trânsito'),
        services.STAGE_CONFERENCIA: _('Conferência'),
        services.STAGE_FATURADO:   _('Faturado'),
        services.STAGE_PARCIAL:    _('Pago em parte'),
        services.STAGE_PAGO:       _('Pago'),
    }


def _iso(valor):
    """Data da URL, ou None. Lixo na query string NUNCA vira erro de tela —
    o comprador não digitou isso, um link velho digitou por ele."""
    from datetime import date
    try:
        return date.fromisoformat((valor or '').strip())
    except ValueError:
        return None


def _recorte(request):
    """Lê e SANEIA o recorte da URL, e devolve o que as duas telas precisam:
    ``(params, linhas, counts, total_geral)``.

    Uma função só para a lista e para o CSV de propósito: a spec §5.3 manda o
    export levar "o MESMO recorte filtrado". Dois caminhos de leitura seriam
    duas chances de divergir, e a divergência apareceria como planilha que não
    bate com a tela — o tipo de bug que ninguém reporta e todo mundo
    desconfia.
    """
    from urllib.parse import urlencode
    todos = services.orders_for_buyer(request.buyer)
    # A contagem sai do conjunto COMPLETO, antes de qualquer filtro (§5.3).
    counts = services.purchase_counts(todos)
    rotulos = _stage_labels()
    f = {
        'q':      (request.GET.get('q') or '').strip()[:80],
        'status': (request.GET.get('status') or '').strip(),
        'period': (request.GET.get('period') or 'any').strip(),
        'from':   (request.GET.get('from') or '').strip(),
        'to':     (request.GET.get('to') or '').strip(),
        'sort':   (request.GET.get('sort') or 'n').strip(),
        'dir':    (request.GET.get('dir') or 'desc').strip(),
    }
    # Saneamento: valor fora do vocabulário vira o default, nunca 404 nem
    # erro. Status VÁLIDO com zero ocorrências continua valendo — escolher
    # "A conferir (0)" tem de mostrar a tela vazia com a frase, não
    # silenciosamente devolver a lista inteira como se nada tivesse sido
    # pedido.
    if f['status'] not in rotulos:
        f['status'] = ''
    if f['period'] not in services.PURCHASE_PERIODS:
        f['period'] = 'any'
    if f['sort'] not in services.PURCHASE_SORTS:
        f['sort'] = 'n'
    if f['dir'] not in ('asc', 'desc'):
        f['dir'] = 'desc'

    linhas = services.filter_purchases(
        todos, q=f['q'], status=f['status'], period=f['period'],
        dt_from=_iso(f['from']), dt_to=_iso(f['to']))
    linhas = services.sort_purchases(linhas, f['sort'],
                                     desc=f['dir'] == 'desc')

    # Query string SEM `page`: é o que os links de ordenação carregam, e é o
    # que faz trocar de coluna voltar para a página 1 (§5.3).
    f['qs'] = urlencode([(k, v) for k, v in (
        ('q', f['q']), ('status', f['status']), ('period', f['period']),
        ('from', f['from']), ('to', f['to'])) if v])
    f['qs_full'] = urlencode([(k, v) for k, v in (
        ('q', f['q']), ('status', f['status']), ('period', f['period']),
        ('from', f['from']), ('to', f['to']),
        ('sort', f['sort']), ('dir', f['dir'])) if v])
    f['rotulos'] = rotulos
    f['filtrando'] = bool(f['q'] or f['status'] or f['period'] != 'any')
    return f, linhas, counts, len(todos)


@partner_required
def compras_list(request):
    """As compras do comprador — todas as empresas, com busca, filtro de
    status, período por DESPACHO, ordenação e paginação (spec v2 §5.3).

    Até 2026-08-26 era "MVP de propósito: sem filtro nem paginação".
    """
    from django.core.paginator import Paginator
    f, linhas, counts, total_geral = _recorte(request)
    bruto = request.GET.get('per') or ''
    por_pagina = int(bruto) if bruto.isdigit() and int(bruto) in (10, 25, 50) else 10
    paginas = Paginator(linhas, por_pagina)
    # `get_page` engole página inválida e fora de faixa — link velho de
    # página 9 depois de um filtro que sobrou 1 página tem de mostrar a
    # última, não estourar.
    pagina = paginas.get_page(request.GET.get('page'))
    return render(request, 'vendas/partner_compras.html', _shell(request, {
        'ordens': pagina.object_list,
        'pagina': pagina,
        'per': por_pagina,
        'per_opcoes': (10, 25, 50),
        'f': f,
        'counts': counts,
        # [(chave, rótulo, quantos)] na ordem do FLUXO, com a contagem do
        # conjunto completo embutida na opção (§5.3). Montado aqui porque o
        # template do Django não indexa dicionário por variável.
        'status_opcoes': [(k, v, counts.get(k, 0))
                          for k, v in f['rotulos'].items()],
        # Quantas esperam ELE (design system v2, 2026-08-19): o rodapé diz o
        # tamanho da fila e quanto dela é trabalho dele. Do conjunto
        # completo — é a fila real, não a que o filtro deixou à vista.
        # SOMA os dois estágios de propósito. O número existe desde antes da
        # divisão e conta a FILA dele: tudo o que ainda vai passar pela sua
        # conferência, esteja a caixa a caminho ou já na bancada. Trocar por
        # só `conferencia` mudaria o significado da frase do rodapé sem
        # ninguém ter pedido — e faria o número cair na cara dele.
        'a_conferir': (counts.get(services.STAGE_A_CONFERIR, 0)
                       + counts.get(services.STAGE_CONFERENCIA, 0)),
        'total_filtrado': len(linhas),
        'total_geral': total_geral,
    }))


# Cabeçalho do CSV — 14 colunas (spec v2 §5.3).
# ⚠ Desvio consciente na 5ª: a spec pede "País" e a `Company` NÃO TEM campo de
# país — o endereço é texto livre de propósito (cada país tem uma estrutura;
# Macau não tem estado, a China inverte a ordem). Emitir "País" vazio seria
# uma coluna que promete e não entrega; o endereço entrega o país e mais. A
# busca da tela já casa contra ele.
_CSV_COLS = ('Lote', 'Ordem', 'Categoria', 'Cliente', 'Cliente — endereço',
             'Transportadora', 'Rastreio', 'Chips', 'CNY total',
             'Taxa travada', 'USD total', 'CNY resultado', 'USD a pagar',
             'Status')


def _csv_num(valor):
    """Número canônico: ponto decimal, sem separador de milhar, sempre. O CSV
    é lido por planilha em quatro idiomas — localizar aqui é o caminho mais
    curto para ¥ 1.234 virar mil duzentos e trinta e quatro em um lugar e
    um vírgula dois em outro."""
    return '' if valor is None else str(valor)


@partner_required
def compras_csv(request):
    """O MESMO recorte filtrado da lista, em CSV (spec v2 §5.3).

    `;` + BOM UTF-8 porque quem abre é Excel em máquina chinesa: sem o BOM os
    acentos viram mojibake, e com vírgula o Excel pt/es/zh não separa colunas.
    """
    import csv
    import io
    from django.http import HttpResponse
    f, linhas, _counts, _total = _recorte(request)
    rotulos = f['rotulos']
    buf = io.StringIO()
    escritor = csv.writer(buf, delimiter=';')
    escritor.writerow(_CSV_COLS)
    for so in linhas:
        fatura = so.fatura
        taxa = so.fx_usd_rate or (so.lot.fx_rate if so.lot_id else None)
        emp = so.company if so.company_id else None
        escritor.writerow([
            so.lot.code if so.lot_id else '',
            so.code,
            # Origem é valor CANÔNICO (phone/pcb/ram): não traduz.
            so.lot.origin if so.lot_id else '',
            emp.name if emp else '',
            ' '.join((emp.address or '').split()) if emp else '',
            so.carrier or '',
            so.tracking or '',
            so.units,
            _csv_num(so.total_rmb or so.est_rmb),
            _csv_num(taxa),
            _csv_num(so.total_usd or so.est_usd),
            # Resultado sai VAZIO enquanto não houver fatura (§5.3) — zero
            # seria dizer que a conferência deu zero.
            _csv_num(fatura.total_rmb if fatura else None),
            # ⚠ `so.fatura_saldo`, não `fatura.balance_usd`: o saldo é
            # materializado dentro do `company_scope` pelo `orders_for_buyer`.
            # Ler a property aqui dispararia o aggregate FORA do escopo e o
            # RLS devolveria zero pagamento em silêncio — o mesmo bug que a
            # lista teve em produção (2026-09-01).
            _csv_num(so.fatura_saldo if fatura else None),
            str(rotulos.get(so.stage, so.stage)),
        ])
    resp = HttpResponse('\ufeff' + buf.getvalue(),
                        content_type='text/csv; charset=utf-8')
    nome = f'compras-{request.buyer.slug}.csv'
    resp['Content-Disposition'] = f'attachment; filename="{nome}"'
    return resp


#: Abas da ficha que a URL pode abrir direto. Vocabulário FECHADO: `?aba=`
#: vem de redirect nosso, mas também de link colado — e um valor livre viraria
#: `hidden` em todas as abas, deixando a ficha sem miolo nenhum.
_ABAS = ('resumo', 'chips', 'categorias', 'pagamentos', 'observacoes')


@partner_required
def compra_detail(request, pk):
    with services.buyer_order(request.buyer, pk) as so:
        aba = request.GET.get('aba')
        ctx = _detalhe(so)
        ctx['aba_inicial'] = aba if aba in _ABAS else 'resumo'
        return render(request, 'vendas/partner_compra.html',
                      _shell(request, ctx))


def _volta_pra_aba(so, aba):
    return redirect(f"{reverse('compras:detail', args=[so.pk])}?aba={aba}")


@partner_required
@require_POST
def compra_observacao(request, pk):
    """Registra uma observação da conferência (spec v2 §6.9).

    Volta para a ABA de observações, não para o topo da ficha: quem acabou de
    escrever quer ver o que escreveu. Cair no Resumo daria a impressão de que
    o registro não pegou.
    """
    with services.buyer_order(request.buyer, pk) as so:
        try:
            services.add_order_note(so, request.POST.get('text'), request.user)
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
        else:
            messages.success(request, _('Observação registrada.'))
        return _volta_pra_aba(so, 'observacoes')


@partner_required
@require_POST
def compra_observacao_remover(request, pk, nota_pk):
    """Remove uma observação — só o autor (spec §3.10).

    POST, não DELETE: é formulário HTML, e formulário HTML não fala DELETE.
    Inventar um verbo que só o JS alcança tiraria a ação de quem está sem JS.
    """
    with services.buyer_order(request.buyer, pk) as so:
        try:
            services.remove_order_note(so, nota_pk, request.user)
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
        else:
            messages.success(request, _('Observação removida.'))
        return _volta_pra_aba(so, 'observacoes')


def _rmb_de(usd, taxa):
    """¥ a partir de US$ pela taxa TRAVADA — leitura derivada (§2.4).

    Inteiro porque RMB não tem centavos na convenção da casa. Sem taxa
    devolve None, e a tela mostra o par sem o lado ¥: inventar o número seria
    exatamente o que a §2.7 proíbe.
    """
    if usd is None or not taxa:
        return None
    return (usd / taxa).quantize(Decimal('1'))


def _pagamentos_com_registro(inv):
    """O histórico com o REGISTRO de cada parcela já traduzido (§3.9).

    Anexado aqui e não no `payment_history` porque o rótulo é PROSA e o
    serviço devolve chave canônica — e porque a tela do CLIENTE consome o
    mesmo serviço sem precisar disto.
    """
    rotulos = _kind_labels()
    registros = services.payment_kinds(inv)
    linhas = services.payment_history(inv, com_autor=True)
    for linha in linhas:
        linha['registro'] = rotulos.get(registros.get(linha['pk']), '')
    return linhas


def _detalhe(so):
    """Tudo que a tela da compra desenha. Roda DENTRO do escopo da empresa."""
    inv = next((i for i in so.invoices.all() if i.status != 'cancelled'), None)
    grupos = services.result_rows(so)
    pendencias = services.draft_pendencias(grupos)
    return {
        'so': so,
        'grupos': grupos,
        'stage': services.order_stage(so),
        'invoice': inv,
        # Rascunho: o valor mostrado é ESTIMADO (re-resolvido na leitura), e
        # `pendencias` nomeia as categorias que faltam cotar. Distinguir os
        # dois casos importa: rascunho SEM pendência é ordem legada (nasceu
        # antes do congelamento automático, F11.6/F1) — ali não falta preço
        # nenhum, falta congelar.
        'estimado': so.status != STATUS_CONFIRMED,
        'pendencias': pendencias[:12],
        'pendencias_extra': max(0, len(pendencias) - 12),
        # Só OV CONFIRMADA, RECEBIDA e ainda sem fatura aceita resultado
        # (dono, 2026-08-18: "ele deve acusar como recebido primeiro para ir
        # pra parte de resultado"). Sem o recebimento a tabela é leitura: não
        # se confere caixa que ainda não chegou.
        'pode_acertar': (so.status == STATUS_CONFIRMED and inv is None
                         and so.received_at is not None),
        # ⚠ ACHADO DE 2026-08-27, e é um buraco antigo. `pode_acertar` responde
        # "ele PODE digitar recusa agora?" e vira falso assim que a fatura
        # nasce. O template usava só ele para decidir se as colunas do
        # resultado existem — então, no instante em que o comprador fechava a
        # conferência, ele PERDIA a vista do que tinha recusado. A informação
        # continuava no banco e sumia da tela dele.
        # `tem_resultado` responde outra pergunta — "a conferência já
        # aconteceu?" — e é ela que decide se as colunas aparecem. A tela não
        # muda de FORMA quando a etapa passa; muda só o que aceita toque.
        # É a mesma distinção que a tela do cliente (`vendas/views.py`) já
        # fazia desde 2026-08-18; a do comprador tinha ficado para trás.
        'tem_resultado': inv is not None,
        # ── REGISTRO LEGADO (dono, 2026-09-01) ───────────────────────────
        # Venda anterior ao sistema, trazida para dentro na reconciliação: o
        # valor está congelado no CABEÇALHO da ordem e as linhas não têm ¥,
        # porque a quebra por categoria nunca existiu (preço repactuado, ou
        # fatura com o part number na forma curta).
        #
        # Sem isto a tela imprimia "sem preço" em TODAS as 88 linhas e ¥ 0,00
        # em cada marca, ao lado de um cabeçalho dizendo US$ 23.224 pago. Para
        # o comprador parecia dado corrompido; era só informação que mora em
        # outro lugar. Uma frase no lugar de 88 repetições.
        #
        # A condição é estreita de propósito — ordem CONFIRMADA, com total
        # congelado, e NENHUMA linha com preço. Ordem em rascunho, ou com
        # preço em algumas linhas e não em outras, continua mostrando
        # "sem preço" linha a linha, que ali é a informação certa.
        'registro_legado': (so.status == STATUS_CONFIRMED
                            and so.total_rmb is not None
                            # Sem `bool(grupos)`: ordem com total congelado e
                            # NENHUMA linha (o CHIP-EXP022026, cujas entradas
                            # não têm chave de preço) é o caso mais legado de
                            # todos — a tabela sai vazia ao lado de um
                            # cabeçalho com valor, e é aí que a frase mais
                            # falta.
                            and not any(l['unit_rmb'] for g in grupos
                                        for l in g['lines'])),
        # Todo chip do lote, PN a PN — a 2ª aba, onde ele confere detalhe
        # por detalhe (dono, 2026-08-18).
        'chips': services.lot_chips(so),
        # 3ª aba: o dicionário da convenção WTC. O comprador recebe as caixas
        # rotuladas com o código e vai se adaptando lendo isto.
        'categorias': services.category_glossary(so),
        # Card de etapas: por onde passou, onde está, para onde vai.
        'steps': services.order_steps(so),
        # Pagamento (dono, 2026-08-18): sempre em US$ — é a moeda em que ele
        # paga. O histórico fica na mesma tela: pagamento parcial é comum.
        # com_autor: aqui o autor é o usuário DELE mesmo. Na tela do cliente
        # esse campo NÃO existe — o nome do comprador é segredo de mercado.
        'pagamentos': _pagamentos_com_registro(inv),
        'hoje': timezone.localdate(),
        # Linha de TOTAIS da tabela de cima (dono, 2026-08-18).
        'total_qty': sum(g['qty'] for g in grupos),
        # Câmbio: TRAVADO no fechamento do lote (PLANO_FX fase C) — a OV
        # herda essa taxa, e é ela que converte o ¥ dele em US$.
        'fx_rate': so.fx_usd_rate or (so.lot.fx_rate if so.lot_id else None),
        'fx_locked_at': so.lot.fx_locked_at if so.lot_id else None,
        # F4: o rastreio que o CLIENTE registrou, clicável quando a
        # transportadora é conhecida.
        'tracking_url': services.tracking_url(so.carrier, so.tracking),
        # ── Duas colunas no topo (dono, 2026-08-18) ──────────────────────
        # ESPERADO é o preço fechado com o cliente: imutável, é o número que
        # ele tinha na mão quando a caixa saiu. FINAL é o que a conferência
        # produziu — muda enquanto o comprador digita e congela na fatura.
        # Separar os dois é o que deixa a diferença legível; um número só,
        # mudando, apagaria a referência.
        'esperado_rmb': (so.total_rmb if so.total_rmb is not None
                         else sum((g['rmb'] for g in grupos), Decimal('0.00'))),
        'esperado_usd': so.total_usd,
        'final_rmb': inv.total_rmb if inv else None,
        'final_usd': inv.total_usd if inv else None,
        'delta_abs': (abs(inv.total_rmb - so.total_rmb)
                      if inv and so.total_rmb is not None else None),
        'total_estimado': sum((g['rmb'] for g in grupos), Decimal('0.00')),
        'total_estimado_usd': sum((g['usd'] for g in grupos), Decimal('0.00')),
        # Uma chave por PÁGINA SERVIDA (spec v2 §5.4): dois cliques no botão
        # mandam a mesma; recarregar é intenção nova e gera outra.
        'idem_key': uuid.uuid4().hex,
        # Observações da conferência (spec §6.9) — lista, com autor e data.
        'observacoes': services.order_notes(so),
        # ── Bloco de PAGAMENTO (spec §6.7 e §6.8) ────────────────────────
        # QUAL carteira depende do arranjo desta empresa (dono, 2026-09-01):
        # com `payout_on_payment` ligado o comprador paga direto ao CLIENTE e
        # o endereço é o dele; desligado, paga o WhatTheChip. Ver
        # `Wallet.for_company` — ela nunca cai de uma para a outra.
        #
        # ⚠ Roda dentro do `buyer_order`, que abre o `company_scope` — a
        # leitura da linha de plataforma passa pelo RLS (vendas/0020). Fora
        # do escopo isto voltaria vazio EM SILÊNCIO e a tela diria "carteira
        # não cadastrada" para uma carteira que existe (CLAUDE.md §7).
        #
        # Sem carteira cadastrada a tela DIZ que não há — nunca desenha
        # endereço em branco, que é convite a colar o errado.
        'carteira': Wallet.for_company(so.company),
        # O par ¥ = US$ do saldo. O DEVIDO nasce em ¥ e vira US$ pela taxa
        # travada; o PAGO nasce em US$. O ¥ do pago e do saldo é leitura
        # conciliável, DERIVADA — nunca base de comparação (§2.4).
        'pago_usd': inv.paid_usd if inv else None,
        'saldo_usd': inv.balance_usd if inv else None,
        'pago_rmb': _rmb_de(inv.paid_usd if inv else None, so.fx_usd_rate or (so.lot.fx_rate if so.lot_id else None)),
        'saldo_rmb': _rmb_de(inv.balance_usd if inv else None, so.fx_usd_rate or (so.lot.fx_rate if so.lot_id else None)),
    }


def _csv_resposta(nome, colunas, linhas):
    """CSV canônico do painel: `;` + BOM UTF-8.

    O separador e o BOM não são gosto: quem abre é Excel em máquina chinesa.
    Sem o BOM os acentos viram mojibake; com vírgula o Excel pt/es/zh não
    separa colunas.
    """
    import csv
    import io
    from django.http import HttpResponse
    buf = io.StringIO()
    escritor = csv.writer(buf, delimiter=';')
    escritor.writerow(colunas)
    escritor.writerows(linhas)
    resp = HttpResponse('\ufeff' + buf.getvalue(),
                        content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{nome}"'
    return resp


def _kind_labels():
    """Rótulo do REGISTRO da parcela. Chaves canônicas, prosa traduzida."""
    return {'integral': _('INTEGRAL'), 'parcial': _('PARCIAL'),
            'quitacao': _('QUITAÇÃO')}


@partner_required
def compra_aba_csv(request, pk, aba):
    """Exporta A ABA ABERTA da ficha (spec v2 §6.10).

    Uma rota por aba, e não um `?aba=`: o nome do arquivo faz parte da
    entrega — `LOT-EMI-041-08-26-chips.csv` diz sozinho o que é, meses depois,
    numa pasta de downloads. Código do lote com `/` trocado por `-`, mesma
    convenção do PDF do resultado (§3.6).
    """
    if aba not in _ABAS:
        raise Http404('Aba desconhecida.')
    with services.buyer_order(request.buyer, pk) as so:
        base = so.lot.code.replace('/', '-') if so.lot_id else so.code
        nome = f'{base}-{aba}.csv'
        fatura = next((i for i in so.invoices.all()
                       if i.status != 'cancelled'), None)

        if aba == 'resumo':
            # As três últimas colunas só existem DEPOIS do recebimento — antes
            # não há recusa para relatar, e coluna vazia num export é pergunta
            # sem resposta. A tabela é a mesma, mais curta (§6.4).
            recebido = so.received_at is not None
            colunas = [_('Marca'), _('Tipo'), _('Capacidade'), _('Caixa WTC'),
                       _('Enviados'), 'CNY unit.', 'CNY esperado']
            if recebido:
                colunas += [_('Recusados'), _('Aprovados'), 'CNY resultado']
            linhas = []
            for grupo in services.result_rows(so):
                for l in grupo['lines']:
                    linha = [grupo['brand'], l['type'], l['capacity'],
                             l['wtc'], l['qty'], _csv_num(l['unit_rmb']),
                             _csv_num(l['total_rmb'])]
                    if recebido:
                        linha += [l['rejected'], l['accepted'],
                                  _csv_num(l.get('pago_rmb'))]
                    linhas.append(linha)

        elif aba == 'chips':
            colunas = [_('Part number'), _('Fabricante'), _('Caixa WTC'),
                       _('Identificação'), _('Chips'), 'CNY unit.', 'CNY total']
            linhas = [[c['pn'], c['brand'], c['wtc'], c['spec'], c['qty'],
                       _csv_num(c['unit_rmb']), _csv_num(c['total_rmb'])]
                      for c in services.lot_chips(so)['linhas']]

        elif aba == 'categorias':
            colunas = [_('Categoria'), _('Tipo'), _('Capacidade'),
                       _('Nesta compra')]
            # ⚠ `no_lote` é BOOLEANO hoje. A spec §6.6 quer a QUANTIDADE
            # ("dizer 'veio' é menos do que dizer quanto veio") — é o mesmo
            # dado que a tela mostra com um visto. Anotado no plano; mudar
            # exige mexer no `category_glossary`, que não é só do comprador.
            linhas = [[c['code'], c['type'], c['capacity'],
                       'sim' if c['no_lote'] else '']
                      for c in services.category_glossary(so)]

        elif aba == 'pagamentos':
            # ⚠ CNY equivalente é LEITURA DERIVADA (§2.4): o pago nasce em US$
            # e vira ¥ pela taxa TRAVADA do lote, nunca pela de hoje.
            taxa = so.fx_usd_rate or (so.lot.fx_rate if so.lot_id else None)
            rotulos = _kind_labels()
            registros = services.payment_kinds(fatura)
            colunas = [_('Data'), _('Registro'), 'USD pago', 'CNY equivalente',
                       _('Referência'), _('Registrado por'), _('Comprovante')]
            linhas = []
            for p in services.payment_history(fatura, com_autor=True):
                cny = ((p['amount_usd'] / taxa).quantize(Decimal('1'))
                       if taxa else None)
                linhas.append([
                    p['paid_at'].strftime('%d/%m/%Y') if p['paid_at'] else '',
                    str(rotulos.get(registros.get(p['pk']), '')),
                    _csv_num(p['amount_usd']), _csv_num(cny),
                    p['reference'], p.get('by') or '',
                    p['receipt_name'] or ('sim' if p['has_receipt'] else '')])

        else:                                    # observacoes
            colunas = [_('Data'), _('Autor'), _('Observação')]
            linhas = [[n['at'].strftime('%d/%m/%Y %H:%M'), n['by'],
                       ' '.join((n['text'] or '').split())]
                      for n in services.order_notes(so)]

        return _csv_resposta(nome, colunas, linhas)


@partner_required
def compra_planilha(request, pk):
    """A compra inteira em planilha: Resumo e Chips, uma aba cada.

    Substitui o CSV por aba no botão Exportar (dono, 2026-09-02). O `aba_csv`
    continua roteado — quem tiver um link salvo não fica sem —, mas nenhuma
    tela aponta mais para ele.

    Passa o `_detalhe(so)` adiante de propósito: é o MESMO dicionário que
    renderiza a ficha. Recalcular dentro do exportador criaria uma segunda
    conta para o mesmo fato, e a primeira divergência entre as duas daria ao
    comprador uma planilha que discorda da tela sem nada que diga qual está
    certa.
    """
    from django.http import HttpResponse
    from .planilha import XLSX, compra_em_planilha
    with services.buyer_order(request.buyer, pk) as so:
        dados, nome = compra_em_planilha(so, _detalhe(so))
        resp = HttpResponse(dados, content_type=XLSX)
        resp['Content-Disposition'] = f'attachment; filename="{nome}"'
        return resp


@partner_required
@require_POST
def compra_recebido(request, pk):
    """"Recebi a caixa" — a etapa que o card precisa (dono, 2026-08-18).

    Idempotente no serviço: a primeira data vale. Quem marca é o COMPRADOR,
    que é quem recebe; o despacho completo (transportadora, rastreio, data de
    envio) é a F4.
    """
    with services.buyer_order(request.buyer, pk) as so:
        services.mark_received(so)
        messages.success(request, _('Recebimento registrado.'))
        return redirect('compras:detail', pk=so.pk)


@partner_required
def compra_resultado_pdf(request, pk):
    """O resultado em PDF — o comprador baixa e manda pro cliente (dono,
    2026-08-18). Só depois de fechado: antes disso não há resultado."""
    from django.http import Http404, HttpResponse
    with services.buyer_order(request.buyer, pk) as so:
        inv = next((i for i in so.invoices.all()
                    if i.status != 'cancelled'), None)
        if inv is None:
            raise Http404('Esta compra ainda não tem resultado fechado.')
        from .pdf import render_result_pdf
        pdf = render_result_pdf(services.result_document(so, inv))
        resp = HttpResponse(pdf, content_type='application/pdf')
        # inline: ele confere na tela antes de mandar. O nome do arquivo é o
        # código do LOTE — é assim que cliente e comprador se referem à caixa.
        resp['Content-Disposition'] = (
            f'inline; filename="{so.lot.code.replace("/", "-")}-resultado.pdf"')
        return resp


@partner_required
@require_POST
def compra_resultado(request, pk):
    """"Fechar resultado": recusas por linha → acerto + fatura, atômico.

    Campo em branco vale ZERO (é o padrão: o comprador digita só o que
    recusou). Quantidade inválida ou maior que a enviada volta para a tela
    com o erro — o ``settle_and_invoice`` valida de novo do lado do modelo,
    então um POST forjado também não passa.
    """
    with services.buyer_order(request.buyer, pk) as so:
        ajustes = {}
        for line in so.lines.all():
            cru = (request.POST.get(f'rej_{line.pk}') or '').strip()
            if not cru:
                continue
            try:
                rej = int(cru)
            except ValueError:
                messages.error(request, _(
                    'Quantidade recusada inválida em %(cat)s.')
                    % {'cat': line.label})
                return redirect('compras:detail', pk=so.pk)
            if rej:
                ajustes[line.pk] = (rej, None)      # sem repreço no MVP
        try:
            services.settle_and_invoice(
                so, ajustes, request.user,
                notes=(request.POST.get('notes') or '').strip())
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
            return redirect('compras:detail', pk=so.pk)
        messages.success(request, _('Resultado fechado — fatura emitida.'))
        # ?pdf=1: a tela abre o PDF do resultado sozinha (dono, 2026-08-18).
        # É o documento que ele manda pro cliente, e o momento de mandar é
        # agora — não depois de lembrar que existe um botão.
        return redirect(f"{reverse('compras:detail', args=[so.pk])}?pdf=1")


@partner_required
@require_POST
def compra_pagar(request, pk):
    """Registra um pagamento da compra, em US$, com o comprovante anexado
    (dono, 2026-08-18).

    Quem registra é o COMPRADOR — é ele quem paga e quem tem o comprovante na
    mão. Parcial é permitido (o `register_payment` barra acima do saldo), e o
    saldo zerado marca a fatura como PAGA.

    ⚠ Pagamento e comprovante entram na MESMA transação: comprovante recusado
    (formato/tamanho) desfaz o pagamento junto. Pagamento registrado com
    comprovante corrompido é pior do que pagamento nenhum — alguém teria que
    descobrir isso na conciliação, meses depois.
    """
    with services.buyer_order(request.buyer, pk) as so:
        inv = next((i for i in so.invoices.all()
                    if i.status != 'cancelled'), None)
        if inv is None:
            messages.error(request, _('Esta compra ainda não tem fatura.'))
            return redirect('compras:detail', pk=so.pk)
        try:
            valor = Decimal((request.POST.get('amount_usd') or '').strip()
                            .replace(',', '.'))
        except (InvalidOperation, TypeError):
            messages.error(request, _('Valor do pagamento inválido.'))
            return redirect('compras:detail', pk=so.pk)
        data = (request.POST.get('paid_at') or '').strip()
        try:
            from datetime import date as _date
            quando = _date.fromisoformat(data) if data else timezone.localdate()
        except ValueError:
            messages.error(request, _('Data do pagamento inválida.'))
            return redirect('compras:detail', pk=so.pk)
        arquivo = request.FILES.get('receipt')
        if arquivo is None:
            messages.error(request, _(
                'Anexe o comprovante — sem ele o pagamento não é registrado.'))
            return redirect('compras:detail', pk=so.pk)
        # ── Duplo-clique (spec v2 §5.4) ─────────────────────────────────
        # Duas guardas, e as duas são necessárias. Esta é o caminho RÁPIDO:
        # o 2º POST chega depois do 1º ter commitado, e a gente responde
        # "já registrado" sem tentar gravar. A corrida de verdade (dois
        # POSTs simultâneos, nenhum enxerga o outro) só a UniqueConstraint
        # resolve — por isso o IntegrityError logo abaixo.
        # ⚠ `all_companies`: dentro do buyer_order o escopo já é o da
        # empresa dona; usar o manager escopado aqui não muda o resultado,
        # mas o não-escopado torna explícito que a busca é por chave, não
        # por tenant.
        idem = (request.POST.get('idem') or '').strip()[:64]
        if idem and Payment.all_companies.filter(
                invoice=inv, idempotency_key=idem).exists():
            messages.info(request, _('Este pagamento já foi registrado.'))
            return redirect('compras:detail', pk=so.pk)
        try:
            with transaction.atomic():
                pagamento = services.register_payment(
                    inv, valor, quando, request.user,
                    reference=(request.POST.get('reference') or '').strip(),
                    idempotency_key=idem)
                services.attach_receipt(pagamento, arquivo)
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
            return redirect('compras:detail', pk=so.pk)
        except IntegrityError:
            # A constraint pegou a corrida: o outro POST já gravou este
            # mesmo pagamento. O atomic() desfez tudo — inclusive o
            # comprovante —, então não sobra meio-registro.
            messages.info(request, _('Este pagamento já foi registrado.'))
            return redirect('compras:detail', pk=so.pk)
        inv.refresh_from_db()
        if inv.balance_usd <= 0:
            messages.success(request, _('Pagamento registrado — fatura quitada.'))
        else:
            messages.success(request, _(
                'Pagamento registrado. Saldo: US$ %(s)s.')
                % {'s': inv.balance_usd})
        return redirect('compras:detail', pk=so.pk)


@partner_required
def compra_comprovante(request, pk, pagamento_pk):
    """Serve o comprovante DO BANCO (ver PaymentReceipt).

    Posse dupla: a OV tem que ser deste comprador (o `buyer_order` já é 404 se
    não for) E o pagamento tem que ser da fatura DESTA OV — senão bastaria
    trocar o número na URL para ler o comprovante de outra compra.
    """
    from django.http import Http404, HttpResponse
    from .models import PaymentReceipt
    with services.buyer_order(request.buyer, pk) as so:
        faturas = [i.pk for i in so.invoices.all()]
        recibo = (PaymentReceipt.all_companies
                  .filter(payment_id=pagamento_pk,
                          payment__invoice_id__in=faturas)
                  .first())
        if recibo is None:
            raise Http404('Comprovante não encontrado.')
        resp = HttpResponse(bytes(recibo.data), content_type=recibo.mime)
        nome = recibo.filename or f'comprovante-{pagamento_pk}'
        resp['Content-Disposition'] = f'inline; filename="{nome}"'
        # Comprovante é DOCUMENTO PRIVADO: nunca em cache compartilhado.
        resp['Cache-Control'] = 'private, no-store'
        return resp
