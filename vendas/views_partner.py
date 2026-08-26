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
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from pricing.views import _fx_info, partner_required

from . import services
from .models import STATUS_CONFIRMED, Payment


def _shell(request, extra=None):
    """Contexto que o ``partner_base.html`` exige (header + sidebar)."""
    ctx = {'buyer': request.buyer, 'fx_info': _fx_info(request.buyer),
           'active_pk': 'compras', 'active_kind': None, 'kind_nav': []}
    ctx.update(extra or {})
    return ctx


@partner_required
def compras_list(request):
    """As compras do comprador — todas as empresas, mais recente primeiro."""
    ordens = services.orders_for_buyer(request.buyer)
    # Quantas esperam ELE (design system v2, 2026-08-19): o rodapé de soma da
    # lista diz o tamanho da fila e quanto dela é trabalho dele. Conta aqui —
    # template não calcula.
    a_conferir = sum(1 for o in ordens if o.stage == services.STAGE_A_CONFERIR)
    return render(request, 'vendas/partner_compras.html',
                  _shell(request, {'ordens': ordens,
                                   'a_conferir': a_conferir}))


@partner_required
def compra_detail(request, pk):
    with services.buyer_order(request.buyer, pk) as so:
        return render(request, 'vendas/partner_compra.html',
                      _shell(request, _detalhe(so)))


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
        'pagamentos': services.payment_history(inv, com_autor=True),
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
        # Uma chave por PÁGINA SERVIDA (spec v2 §5.4): dois cliques no botão
        # mandam a mesma; recarregar é intenção nova e gera outra.
        'idem_key': uuid.uuid4().hex,
    }


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
